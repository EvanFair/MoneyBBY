const API_BASE = ""; // Relative path matches FastAPI server mount

document.addEventListener("DOMContentLoaded", () => {
    initTabs();
    initFeedCuration();
    initEpisodes();
    initSocialAccounts();
    initDistribute();
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
            } else if (targetTab === "accounts") {
                renderAccountCards();
            } else if (targetTab === "distribute") {
                loadDistributeEpisodes();
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
    const feedLimitVal = document.getElementById("feed-limit-val");
    if (feedLimit) {
        feedLimit.addEventListener("input", (e) => {
            const val = e.target.value;
            if (feedLimitVal) {
                feedLimitVal.textContent = val == 100 ? "All" : val;
            }
        });
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
    
    // If limit is 100, we show all (omit limit param)
    const limitParam = limit == 100 ? "" : `&limit=${limit}`;

    Promise.all([
        fetch(`${API_BASE}/api/stories?status=scraped${limitParam}`).then(res => res.json()),
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

        <div style="display:flex; justify-content:space-be