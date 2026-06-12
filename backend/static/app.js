const API_BASE = ""; // Relative path matches FastAPI server mount

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initFeedCuration();
    initEpisodes();
    initSettings();
});

// Tab Switching
function initTabs() {
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabs = document.querySelectorAll(".tab-content");

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetTab = btn.getAttribute("data-tab");

            navButtons.forEach(b => b.classList.remove("active"));
            tabs.forEach(t => t.classList.remove("active"));

            btn.classList.add("active");
            document.getElementById(`tab-${targetTab}`).classList.add("active");

            if (targetTab === "curate") {
                loadCurationStories();
            } else if (targetTab === "episodes") {
                loadEpisodesList();
            } else if (targetTab === "settings") {
                loadSources();
            }
        });
    });
}

// ─── Feed Curation ───────────────────────────────────────────────────────────

function initFeedCuration() {
    const btnScrape = document.getElementById("btn-scrape");
    if (btnScrape) {
        btnScrape.addEventListener("click", () => {
            showToast("Scraping started in background. Refreshing in 10s...");
            fetch(`${API_BASE}/api/scrape`, { method: "POST" })
                .then(res => res.json())
                .then(() => {
                    setTimeout(loadCurationStories, 10000);
                });
        });
    }

    const feedLimit = document.getElementById("feed-limit");
    if (feedLimit) {
        feedLimit.addEventListener("change", () => {
            loadCurationStories();
        });
    }

    loadCurationStories();
}

function loadCurationStories() {
    const container = document.getElementById("story-list-container");
    if (!container) return;

    const limitEl = document.getElementById("feed-limit");
    const limit = limitEl ? limitEl.value : 10;

    Promise.all([
        fetch(`${API_BASE}/api/stories?status=scraped&limit=${limit}`).then(res => res.json()),
        fetch(`${API_BASE}/api/stories?status=approved`).then(res => res.json())
    ]).then(([scraped, approved]) => {
        document.getElementById("stat-scraped").textContent = scraped.length;
        document.getElementById("stat-approved").textContent = approved.length;

        if (scraped.length === 0) {
            container.innerHTML = `
                <div class="detail-placeholder">
                    <span>🎉</span>
                    <h3>No new stories pending review</h3>
                    <p>Click "Scrape New Stories" to fetch fresh AI news feeds!</p>
                </div>`;
        } else {
            container.innerHTML = scraped.map(story => renderStoryCard(story)).join("");
        }

        loadApprovedToday();
        loadTrendingTags();
    }).catch(() => {
        container.innerHTML = `<div class="loader" style="color:var(--danger)">Failed to load stories. Make sure backend is running.</div>`;
    });
}

function renderStoryCard(story) {
    // Image gallery
    let imagesHtml = "";
    if (story.images_json) {
        try {
            const images = JSON.parse(story.images_json);
            if (images && images.length > 0) {
                const imgs = images.slice(0, 5).map(img => {
                    const src = typeof img === 'string' ? img : (img.local_path || img.url || '');
                    return `<img src="${src}" alt="story image" loading="lazy">`;
                }).join("");
                imagesHtml = `<div class="story-images">${imgs}</div>`;
            }
        } catch (e) { /* ignore parse errors */ }
    }

    // Value score badge
    let valueBadge = "";
    if (story.value_score != null) {
        valueBadge = `<span class="value-badge">⭐ ${story.value_score}/10</span>`;
    }

    // Value explanation
    let valueExplanation = "";
    if (story.value_explanation) {
        valueExplanation = `<p class="value-explanation">${story.value_explanation}</p>`;
    }

    // Niche tags
    let nicheTagsHtml = "";
    if (story.niche_tags) {
        let tags = [];
        try {
            const parsed = JSON.parse(story.niche_tags);
            if (Array.isArray(parsed)) tags = parsed;
        } catch (e) {
            tags = story.niche_tags.split(",").map(t => t.trim()).filter(Boolean);
        }
        if (tags.length > 0) {
            nicheTagsHtml = `<div class="niche-tags">${tags.map(t => `<span class="niche-tag">${t}</span>`).join("")}</div>`;
        }
    }

    // Categories
    const categories = [
        "Model Release",
        "Open Source Repository",
        "Research Paper",
        "Hardware & GPU Infrastructure",
        "Developer Tooling & SDKs",
        "AI SaaS & Consumer Product",
        "Industry & Startups",
        "Robotics & Embodied AI",
        "Safety & Alignment"
    ];
    const categoryOptions = categories.map(cat =>
        `<option value="${cat}" ${story.category === cat ? "selected" : ""}>${cat}</option>`
    ).join("");

    return `
        <div class="story-card" id="story-card-${story.id}">
            <div class="story-card-header">
                <div>
                    <h3 class="story-title">${story.title}</h3>
                    <div class="story-meta">
                        <span>Source: <strong class="story-source">${story.source}</strong></span>
                        <span>URL: <a href="${story.url}" target="_blank" style="color:var(--primary);text-decoration:none;">Link</a></span>
                        ${valueBadge}
                    </div>
                    ${valueExplanation}
                    ${nicheTagsHtml}
                </div>
            </div>
            ${imagesHtml}
            <div class="story-body">
                <label>Clean Host Summary</label>
                <textarea rows="3" id="summary-${story.id}">${story.clean_summary || ""}</textarea>
            </div>
            <div class="story-actions">
                <select class="category-select" id="category-${story.id}">
                    ${categoryOptions}
                </select>
                <div class="action-btns">
                    <button class="btn-action btn-reject" onclick="curateStory(${story.id}, 'rejected')">Reject</button>
                    <button class="btn-action btn-approve" onclick="curateStory(${story.id}, 'approved')">Approve & Save</button>
                </div>
            </div>
        </div>
    `;
}

window.curateStory = function(storyId, status) {
    const summary = document.getElementById(`summary-${storyId}`).value;
    const category = document.getElementById(`category-${storyId}`).value;

    fetch(`${API_BASE}/api/stories/${storyId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            status: status,
            clean_summary: summary,
            category: category
        })
    }).then(res => res.json()).then(() => {
        showToast(status === "approved" ? "Story Approved!" : "Story Rejected.");
        const card = document.getElementById(`story-card-${storyId}`);
        if (card) {
            card.style.opacity = 0;
            card.style.transform = "scale(0.95)";
            card.style.transition = "all 0.3s ease";
            setTimeout(() => {
                loadCurationStories();
            }, 300);
        }
    });
};

function loadApprovedToday() {
    const listContainer = document.getElementById("approved-today-list");
    const summaryText = document.getElementById("approved-summary-text");

    fetch(`${API_BASE}/api/stories?status=approved`)
        .then(res => res.json())
        .then(approved => {
            if (approved.length === 0) {
                if (listContainer) listContainer.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">No approved stories yet.</p>`;
                if (summaryText) summaryText.textContent = "Approve stories to see a summary...";
                return;
            }

            if (listContainer) {
                listContainer.innerHTML = approved.map(s => `
                    <div class="approved-story-item">
                        <span class="approved-story-dot"></span>
                        <span>${s.title}</span>
                    </div>
                `).join("");
            }
        })
        .catch(() => {});

    // Fetch episode direction summary
    fetch(`${API_BASE}/api/approved-summary`)
        .then(res => res.json())
        .then(data => {
            if (summaryText && data && data.summary) {
                summaryText.textContent = data.summary;
            }
        })
        .catch(() => {});
}

function loadTrendingTags() {
    const container = document.getElementById("trending-tags-container");
    if (!container) return;

    fetch(`${API_BASE}/api/trending-tags`)
        .then(res => res.json())
        .then(tags => {
            if (!tags || tags.length === 0) {
                container.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">Scrape and clean stories to see trends...</p>`;
                return;
            }

            container.innerHTML = tags.map(tag => `
                <div class="trending-tag-item">
                    <span>${tag.tag || tag.name}</span>
                    <span class="trending-tag-count">${tag.count}</span>
                </div>
            `).join("");
        })
        .catch(() => {
            container.innerHTML = `<p style="color:var(--text-muted);font-size:13px;">Scrape and clean stories to see trends...</p>`;
        });
}

// ─── Episodes Logic ──────────────────────────────────────────────────────────

function initEpisodes() {
    const btnCreate = document.getElementById("btn-create-episode");
    if (btnCreate) {
        btnCreate.addEventListener("click", () => {
            btnCreate.disabled = true;
            btnCreate.textContent = "Synthesizing & Rendering...";
            showToast("Generating Episode and rendering final MP4. This takes about 30 seconds.");

            fetch(`${API_BASE}/api/episodes`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: "AIPulse Daily Briefing" })
            })
            .then(res => {
                if (!res.ok) throw new Error("Failed to create episode. Verify you have approved stories.");
                return res.json();
            })
            .then(() => {
                showToast("Episode created! Render running in background.");
                btnCreate.disabled = false;
                btnCreate.innerHTML = `<span>🎙</span> Generate Daily Episode`;
                loadEpisodesList();
            })
            .catch(err => {
                showToast(err.message);
                btnCreate.disabled = false;
                btnCreate.innerHTML = `<span>🎙</span> Generate Daily Episode`;
            });
        });
    }
}

function loadEpisodesList() {
    const container = document.getElementById("episodes-list-container");
    if (!container) return;

    fetch(`${API_BASE}/api/episodes`)
        .then(res => res.json())
        .then(episodes => {
            if (episodes.length === 0) {
                container.innerHTML = `<div class="loader">No episodes generated yet.</div>`;
                return;
            }

            container.innerHTML = episodes.map((ep, idx) => `
                <div class="episode-card ${idx === 0 ? "active" : ""}" onclick="selectEpisode(${ep.id}, this)">
                    <h3>${ep.title}</h3>
                    <span>ID: ${ep.id} | Status: <strong style="color:var(--primary)">${ep.status}</strong></span>
                </div>
            `).join("");

            if (episodes.length > 0) {
                viewEpisodeDetails(episodes[0].id);
            }
        });
}

window.selectEpisode = function(epId, element) {
    document.querySelectorAll(".episode-card").forEach(c => c.classList.remove("active"));
    element.classList.add("active");
    viewEpisodeDetails(epId);
};

function viewEpisodeDetails(epId) {
    const container = document.getElementById("episode-detail-container");
    if (!container) return;

    container.innerHTML = `<div class="loader">Loading episode outputs...</div>`;

    fetch(`${API_BASE}/api/episodes/${epId}`)
        .then(res => res.json())
        .then(ep => {
            const script = JSON.parse(ep.script_json);

            let audioBlock = `<p style="color:var(--text-muted)">Audio file synthesizing...</p>`;
            if (ep.status === "audio_ready" || ep.status === "video_ready") {
                audioBlock = `
                    <div class="media-item">
                        <label>🔊 Stitched Podcast Audio</label>
                        <audio controls src="${API_BASE}/output/episode_${ep.id}.mp3"></audio>
                    </div>`;
            }

            let videoBlock = `<p style="color:var(--text-muted)">Video file rendering...</p>`;
            if (ep.status === "video_ready") {
                videoBlock = `
                    <div class="media-item">
                        <label>📺 Rendered YouTube Video</label>
                        <video controls src="${API_BASE}/output/episode_${ep.id}.mp4"></video>
                    </div>`;
            }

            container.innerHTML = `
                <h2>${ep.title}</h2>
                <div class="media-players">
                    ${audioBlock}
                    ${videoBlock}
                </div>
                <div class="transcript-box">
                    <h3>Conversation Script</h3>
                    ${script.map(line => `
                        <div class="bubble bubble-${line.speaker}">
                            <div class="bubble-name">${line.speaker}</div>
                            <div>${line.text}</div>
                        </div>
                    `).join("")}
                </div>
            `;
        });
}

// ─── Settings / Sources Logic ────────────────────────────────────────────────

function initSettings() {
    // Sources load when the settings tab is clicked
    const btnAddSource = document.getElementById("btn-add-source");
    if (btnAddSource) {
        btnAddSource.addEventListener("click", () => {
            const name = document.getElementById("source-name").value.trim();
            const url = document.getElementById("source-url").value.trim();
            const type = document.getElementById("source-type").value;
            const volume = document.getElementById("source-volume").value;

            if (!name || !url) {
                showToast("Please provide both a name and URL.");
                return;
            }

            fetch(`${API_BASE}/api/sources`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, url, type, volume_limit: parseInt(volume), enabled: 1 })
            })
            .then(res => res.json())
            .then(() => {
                showToast("Source added successfully!");
                document.getElementById("source-name").value = "";
                document.getElementById("source-url").value = "";
                loadSources();
            })
            .catch(() => showToast("Failed to add source."));
        });
    }
}

function loadSources() {
    const container = document.getElementById("sources-list-container");
    if (!container) return;

    fetch(`${API_BASE}/api/sources`)
        .then(res => res.json())
        .then(sources => {
            if (!sources || sources.length === 0) {
                container.innerHTML = `<div class="loader">No sources configured yet. Add one above!</div>`;
                return;
            }

            container.innerHTML = sources.map(src => {
                const isEnabled = src.enabled === 1 || src.enabled === true;
                return `
                    <div class="source-card" id="source-card-${src.id}">
                        <div class="source-info">
                            <h4>${src.name}</h4>
                            <span>${src.url}</span>
                            <span class="niche-tag" style="margin-top:4px;width:fit-content;">${src.type || "rss"}</span>
                        </div>
                        <div class="source-controls">
                            <div class="volume-slider-container">
                                <input type="range" min="1" max="30" value="${src.volume_limit || 10}" class="volume-slider"
                                    onchange="updateSourceVolume(${src.id}, this.value, this)"
                                    oninput="this.nextElementSibling.textContent = this.value">
                                <span class="volume-label">${src.volume_limit || 10}</span>
                            </div>
                            <label class="toggle-switch">
                                <input type="checkbox" ${isEnabled ? "checked" : ""}
                                    onchange="toggleSource(${src.id}, this.checked)">
                                <span class="toggle-slider"></span>
                            </label>
                            <button class="btn-danger" onclick="deleteSource(${src.id})">Delete</button>
                        </div>
                    </div>
                `;
            }).join("");
        })
        .catch(() => {
            container.innerHTML = `<div class="loader" style="color:var(--danger)">Failed to load sources.</div>`;
        });
}

window.toggleSource = function(sourceId, checked) {
    fetch(`${API_BASE}/api/sources/${sourceId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: checked ? 1 : 0 })
    })
    .then(res => res.json())
    .then(() => showToast(checked ? "Source enabled." : "Source disabled."))
    .catch(() => showToast("Failed to update source."));
};

window.updateSourceVolume = function(sourceId, value, el) {
    const label = el.nextElementSibling;
    if (label) label.textContent = value;

    fetch(`${API_BASE}/api/sources/${sourceId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ volume_limit: parseInt(value) })
    })
    .then(res => res.json())
    .then(() => showToast(`Volume limit set to ${value}.`))
    .catch(() => showToast("Failed to update volume."));
};

window.deleteSource = function(sourceId) {
    fetch(`${API_BASE}/api/sources/${sourceId}`, { method: "DELETE" })
        .then(res => res.json())
        .then(() => {
            showToast("Source deleted.");
            loadSources();
        })
        .catch(() => showToast("Failed to delete source."));
};

// ─── Toast Notification ──────────────────────────────────────────────────────

function showToast(message) {
    const toast = document.getElementById("toast");
    if (toast) {
        toast.textContent = message;
        toast.classList.add("show");
        setTimeout(() => {
            toast.classList.remove("show");
        }, 4000);
    }
}
