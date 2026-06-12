const API_BASE = ""; // Relative path matches FastAPI server mount

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initFeedCuration();
    initEpisodes();
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
            }
        });
    });
}

// Curation Logic
function initFeedCuration() {
    const btnScrape = document.getElementById("btn-scrape");
    if (btnScrape) {
        btnScrape.addEventListener("click", () => {
            showToast("Scraping started in background. Refreshing in 10s...");
            fetch(`${API_BASE}/api/scrape`, { method: "POST" })
                .then(res => res.json())
                .then(data => {
                    setTimeout(loadCurationStories, 10000);
                });
        });
    }
    loadCurationStories();
}

function loadCurationStories() {
    const container = document.getElementById("story-list-container");
    if (!container) return;

    // Load counts and scraped list
    Promise.all([
        fetch(`${API_BASE}/api/stories?status=scraped`).then(res => res.json()),
        fetch(`${API_BASE}/api/stories?status=approved`).then(res => res.json())
    ]).then(([scraped, approved]) => {
        document.getElementById("stat-scraped").textContent = scraped.length;
        document.getElementById("stat-approved").textContent = approved.length;

        if (scraped.length === 0) {
            container.innerHTML = `
                <div class="detail-placeholder">
                    <span>🎉</span>
                    <h3>No new stories pending review</h3>
                    <p>Click "Scrape New Stories" to fetch fresh feeds from Good News Network!</p>
                </div>`;
            return;
        }

        container.innerHTML = scraped.map(story => `
            <div class="story-card" id="story-card-${story.id}">
                <div class="story-card-header">
                    <div>
                        <h3 class="story-title">${story.title}</h3>
                        <div class="story-meta">
                            <span>Source: <strong class="story-source">${story.source}</strong></span>
                            <span>URL: <a href="${story.url}" target="_blank" style="color:var(--primary);text-decoration:none;">Link</a></span>
                        </div>
                    </div>
                </div>
                <div class="story-body">
                    <label>Clean Host Summary</label>
                    <textarea rows="3" id="summary-${story.id}">${story.clean_summary || ""}</textarea>
                </div>
                <div class="story-actions">
                    <select class="category-select" id="category-${story.id}">
                        <option value="General Wholesome" ${story.category === "General Wholesome" ? "selected" : ""}>General Wholesome</option>
                        <option value="Animals" ${story.category === "Animals" ? "selected" : ""}>Animals</option>
                        <option value="Human Kindness" ${story.category === "Human Kindness" ? "selected" : ""}>Human Kindness</option>
                        <option value="Nature & Environment" ${story.category === "Nature & Environment" ? "selected" : ""}>Nature & Environment</option>
                        <option value="Science & Innovation" ${story.category === "Science & Innovation" ? "selected" : ""}>Science & Innovation</option>
                    </select>
                    <div class="action-btns">
                        <button class="btn-action btn-reject" onclick="curateStory(${story.id}, 'rejected')">Reject</button>
                        <button class="btn-action btn-approve" onclick="curateStory(${story.id}, 'approved')">Approve & Save</button>
                    </div>
                </div>
            </div>
        `).join("");
    }).catch(err => {
        container.innerHTML = `<div class="loader" style="color:var(--danger)">Failed to load stories. Make sure backend is running.</div>`;
    });
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
    }).then(res => res.json()).then(data => {
        showToast(status === "approved" ? "Story Approved!" : "Story Rejected.");
        // Fade out element
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

// Episodes Logic
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
                body: JSON.stringify({ title: "Daily Wholesome Round-up" })
            })
            .then(res => {
                if (!res.ok) throw new Error("Failed to create episode. Verify you have approved stories.");
                return res.json();
            })
            .then(data => {
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

            // Auto-select first episode
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

// Toast Notification helper
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
