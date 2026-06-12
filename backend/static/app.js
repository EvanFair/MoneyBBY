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

window.loadedStories = [];

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

    // Modal close bindings
    const modalClose = document.getElementById("modal-close");
    if (modalClose) {
        modalClose.addEventListener("click", closeStoryModal);
    }
    const modal = document.getElementById("story-modal");
    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                closeStoryModal();
            }
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
        
        window.loadedStories = scraped; // Store loaded stories globally for modal lookup

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
    // Value score badge
    let valueBadge = "";
    if (story.value_score != null) {
        valueBadge = `<span class="value-badge">⭐ ${story.value_score}/10</span>`;
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
            nicheTagsHtml = `<div class="niche-tags">${tags.slice(0, 3).map(t => `<span class="niche-tag">${t}</span>`).join("")}</div>`;
        }
    }

    // Short teaser
    let teaserSummary = story.clean_summary || story.summary || "Click card to view scraped content and summary details...";
    if (teaserSummary.length > 150) {
        teaserSummary = teaserSummary.substring(0, 150) + "...";
    }

    return `
        <div class="story-card-compact" id="story-card-${story.id}" onclick="openStoryModal(${story.id})">
            <div class="story-card-compact-header">
                <h3 class="story-card-compact-title">${story.title}</h3>
                ${valueBadge}
            </div>
            <p class="story-card-compact-summary">${teaserSummary}</p>
            <div class="story-card-compact-meta">
                <span>Source: <strong class="story-card-compact-source">${story.source}</strong></span>
                <span>Category: <strong>${story.category || "Uncategorized"}</strong></span>
                ${nicheTagsHtml}
            </div>
        </div>
    `;
}

window.openStoryModal = function(storyId) {
    const story = window.loadedStories.find(s => s.id === storyId);
    if (!story) return;

    const modal = document.getElementById("story-modal");
    const modalBody = document.getElementById("modal-body-content");
    if (!modal || !modalBody) return;

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

    // Multiple Image gallery
    let imagesHtml = "";
    if (story.images_json) {
        try {
            const images = JSON.parse(story.images_json);
            if (images && images.length > 0) {
                const imgs = images.map(img => {
                    const src = typeof img === 'string' ? img : (img.local_path || img.url || '');
                    return `<img src="${src}" alt="story image" onclick="window.open('${src}', '_blank')">`;
                }).join("");
                imagesHtml = `
                    <span class="modal-section-title">🖼️ Scraped Media / Images</span>
                    <div class="modal-image-gallery">${imgs}</div>
                `;
            }
        } catch (e) {}
    }

    // Value score details
    let valueBadge = story.value_score != null ? `<span class="value-badge">⭐ Value Score: ${story.value_score}/10</span>` : "";
    let valueExplanationHtml = story.value_explanation ? `<p class="value-explanation" style="font-size:14px; margin-top:8px; color:var(--text-secondary);"><strong>Practical Value:</strong> ${story.value_explanation}</p>` : "";

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
            nicheTagsHtml = `<div class="niche-tags" style="margin-top:8px;">${tags.map(t => `<span class="niche-tag">${t}</span>`).join("")}</div>`;
        }
    }

    // Full article content
    let fullTextHtml = "";
    if (story.full_text) {
        fullTextHtml = `
            <span class="modal-section-title">📄 Full Scraped Web Page Content</span>
            <div class="modal-full-text-box">${story.full_text}</div>
        `;
    } else if (story.summary) {
        fullTextHtml = `
            <span class="modal-section-title">📄 Raw Summary / Content Snippet</span>
            <div class="modal-full-text-box">${story.summary}</div>
        `;
    }

    modalBody.innerHTML = `
        <h3 class="story-title" style="font-size:20px; line-height:1.4; margin-bottom:12px; color:var(--text-primary); font-family:'Outfit',sans-serif;">${story.title}</h3>
        <div class="modal-story-meta">
            <span>Source: <strong class="story-source">${story.source}</strong></span>
            <span>URL: <a href="${story.url}" target="_blank" style="color:var(--primary); text-decoration:none; font-weight:600;">Open Source Link ↗</a></span>
            ${valueBadge}
        </div>

        ${valueExplanationHtml}
        ${nicheTagsHtml}

        ${imagesHtml}

        ${fullTextHtml}

        <div style="margin-top:20px; display:flex; flex-direction:column; gap:8px;">
            <label style="font-size:11px; font-weight:800; text-transform:uppercase; color:var(--text-muted); letter-spacing:0.5px;">Clean Host Summary (Edit details to approve)</label>
            <textarea id="modal-summary-${story.id}" rows="4" style="width:100%; background:rgba(0,0,0,0.3); border:1px solid var(--border-glass); border-radius:10px; padding:12px; color:var(--text-primary); font-family:inherit; font-size:14px; line-height:1.5; resize:vertical;">${story.clean_summary || ""}</textarea>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:20px; padding-top:16px; border-top:1px solid var(--border-glass);">
            <div style="display:flex; align-items:center; gap:12px;">
                <label style="font-size:13px; font-weight:600; color:var(--text-secondary);">Category:</label>
                <select class="category-select" id="modal-category-${story.id}">
                    ${categoryOptions}
                </select>
            </div>
            <div class="action-btns">
                <button class="btn-action btn-reject" onclick="curateStoryFromModal(${story.id}, 'rejected')">Reject</button>
                <button class="btn-action btn-approve" onclick="curateStoryFromModal(${story.id}, 'approved')">Approve & Save</button>
            </div>
        </div>
    `;

    modal.classList.add("open");
};

window.closeStoryModal = function() {
    const modal = document.getElementById("story-modal");
    if (modal) modal.classList.remove("open");
};

window.curateStoryFromModal = function(storyId, status) {
    const summary = document.getElementById(`modal-summary-${storyId}`).value;
    const category = document.getElementById(`modal-category-${storyId}`).value;

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
        closeStoryModal();

        const card = document.getElementById(`story-card-${storyId}`);
        if (card) {
            card.style.opacity = 0;
            card.style.transform = "scale(0.95)";
            card.style.transition = "all 0.3s ease";
            setTimeout(() => {
                loadCurationStories();
            }, 300);
        } else {
            loadCurationStories();
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
