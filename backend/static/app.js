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
        body: JSON.stringify({ status, clean_summary: summary, category })
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
                <div class="media-players">${audioBlock}${videoBlock}</div>
                <div class="transcript-box">
                    <h3>Conversation Script</h3>
                    ${script.map(line => `
                        <div class="bubble bubble-${line.speaker}">
                            <div class="bubble-name">${line.speaker}</div>
                            <div>${line.text}</div>
                        </div>`).join("")}
                </div>`;
        });
}

// =============================================
// PLATFORM & CONTENT TYPE DEFINITIONS
// =============================================

const PLATFORMS = [
    { id: 'youtube',   name: 'YouTube',   emoji: '▶',  color: '#FF4444', colorRgb: '255,68,68',   hint: 'Full videos + Shorts' },
    { id: 'instagram', name: 'Instagram', emoji: '◉',  color: '#E1306C', colorRgb: '225,48,108',  hint: 'Reels, Carousels, Stories, Posts' },
    { id: 'tiktok',    name: 'TikTok',    emoji: '♪',  color: '#69C9D0', colorRgb: '105,201,208', hint: 'Short video · hook in 3s' },
    { id: 'facebook',  name: 'Facebook',  emoji: 'f',  color: '#1877F2', colorRgb: '24,119,242',  hint: 'Video, Reels, Carousels, Stories' },
    { id: 'twitter',   name: 'X',         emoji: '𝕏',  color: '#e7e9ea', colorRgb: '231,233,234', hint: 'Posts and Threads · 280 chars' },
    { id: 'linkedin',  name: 'LinkedIn',  emoji: 'in', color: '#0A66C2', colorRgb: '10,102,194',  hint: 'Posts and Videos · professional' },
    { id: 'pinterest', name: 'Pinterest', emoji: '✦',  color: '#E60023', colorRgb: '230,0,35',    hint: 'Pins and Video Pins' },
    { id: 'threads',   name: 'Threads',   emoji: '@',  color: '#aaaaaa', colorRgb: '170,170,170', hint: 'Text posts up to 500 chars' },
    { id: 'bluesky',   name: 'Bluesky',   emoji: '◈',  color: '#0085FF', colorRgb: '0,133,255',   hint: 'Posts up to 300 chars' },
    { id: 'tumblr',    name: 'Tumblr',    emoji: 't',  color: '#35465C', colorRgb: '53,70,92',    hint: 'Blog-style posts and media' },
];

const PLATFORM_TYPES = [
    // ── YouTube ──────────────────────────────────────────────
    { typeId: 'youtube-video',        platform: 'youtube',   label: 'Full Video',
      specs: 'MP4 · 16:9 · up to 15 min', charLimit: 5000, charLimitLabel: '5,000',
      captionFn: (ep, fl) => `🎙️ ${ep.title}\n\nA feel-good episode packed with wholesome stories to brighten your day.${fl ? `\n\n"${fl}"` : ''}\n\n🔔 Subscribe for your weekly good news fix!\n\n#GoodNewsCast #GoodNews #PositiveNews #Podcast #Wholesome` },
    { typeId: 'youtube-short',        platform: 'youtube',   label: 'Short',
      specs: 'MP4 · 9:16 · max 60 sec', charLimit: 5000, charLimitLabel: '5,000',
      captionFn: (ep, fl) => `${fl ? `"${fl}" ` : ''}Good news every week 🌱 #GoodNewsCast #Shorts #GoodNews #PositiveVibes` },

    // ── Instagram ─────────────────────────────────────────────
    { typeId: 'instagram-reel',       platform: 'instagram', label: 'Reel',
      specs: '9:16 · 60–90 sec', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `✨ ${ep.title} ✨\n\nYour daily dose of good news is here! 🌟${fl ? `\n\n💬 "${fl}"` : ''}\n\nDouble tap if you needed this today 💛\n\n#GoodNewsCast #GoodVibesOnly #PositiveNews #FeelGood #Reel` },
    { typeId: 'instagram-carousel',   platform: 'instagram', label: 'Carousel',
      specs: '1:1 · up to 10 slides', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `Swipe for your weekly good news roundup 👉\n\n${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\n💛 Save this for when you need a pick-me-up.\n\n#GoodNews #GoodNewsCast #Wholesome #Carousel` },
    { typeId: 'instagram-story',      platform: 'instagram', label: 'Story',
      specs: '9:16 · 15 sec', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `✨ New episode is live! Tap to listen 🎙️` },
    { typeId: 'instagram-post',       platform: 'instagram', label: 'Post',
      specs: '1:1 or 4:5 · static', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `🌿 ${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nGood news is out there — we just go find it for you 💛\n\n#GoodNewsCast #GoodNews #PositiveNews #Wholesome` },

    // ── TikTok ────────────────────────────────────────────────
    { typeId: 'tiktok-video',         platform: 'tiktok',    label: 'Video',
      specs: '9:16 · 15–60 sec', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `good news hits different 🌱 ${fl ? `"${fl}" ` : ''}#goodnews #positivity #feelgood #fyp #wholesome #goodnewscast` },

    // ── Facebook ──────────────────────────────────────────────
    { typeId: 'facebook-video',       platform: 'facebook',  label: 'Video',
      specs: 'MP4 · 16:9 · up to 240 min', charLimit: 63206, charLimitLabel: '63,206',
      captionFn: (ep, fl) => `🌟 New Episode: ${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nTune in for your weekly dose of genuinely good news 🎙️\n\n#GoodNews #GoodNewsCast #Community #Podcast` },
    { typeId: 'facebook-reel',        platform: 'facebook',  label: 'Reel',
      specs: '9:16 · up to 90 sec', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `✨ ${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nYour good news fix is here 💛 #GoodNewsCast #FeelGood` },
    { typeId: 'facebook-carousel',    platform: 'facebook',  label: 'Carousel',
      specs: '1:1 · up to 10 cards', charLimit: 63206, charLimitLabel: '63,206',
      captionFn: (ep, fl) => `📰 This week's good news roundup:\n\n${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nSwipe through the highlights! #GoodNews #GoodNewsCast` },
    { typeId: 'facebook-story',       platform: 'facebook',  label: 'Story',
      specs: '9:16 · 20 sec', charLimit: 2200, charLimitLabel: '2,200',
      captionFn: (ep, fl) => `New episode is live! 🎙️✨ Tap to listen — ${ep.title}` },

    // ── X / Twitter ───────────────────────────────────────────
    { typeId: 'twitter-post',         platform: 'twitter',   label: 'Post',
      specs: '280 chars · 2m20s video', charLimit: 280, charLimitLabel: '280',
      captionFn: (ep, fl) => `🎙️ New ep: "${ep.title}" — your weekly dose of genuinely good news 🌍✨ #GoodNewsCast` },
    { typeId: 'twitter-thread',       platform: 'twitter',   label: 'Thread',
      specs: '280 chars per tweet', charLimit: 280, charLimitLabel: '280/tweet',
      captionFn: (ep, fl) => `🧵 ${ep.title}\n\n1/ This week we covered stories that will actually make you feel good about the world.\n\n${fl ? `2/ "${fl}"\n\n` : ''}3/ Full episode on all podcast platforms 🎙️ #GoodNewsCast #GoodNews` },

    // ── LinkedIn ──────────────────────────────────────────────
    { typeId: 'linkedin-post',        platform: 'linkedin',  label: 'Post',
      specs: '3,000 chars', charLimit: 3000, charLimitLabel: '3,000',
      captionFn: (ep, fl) => `In a world dominated by negative headlines, we need reminders that good things are happening every day.\n\n${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nWhat positive news have you come across this week?\n\n#GoodNews #WellBeing #Podcast #PositiveLeadership` },
    { typeId: 'linkedin-video',       platform: 'linkedin',  label: 'Video',
      specs: 'MP4 · up to 10 min', charLimit: 3000, charLimitLabel: '3,000',
      captionFn: (ep, fl) => `New episode of GoodNewsCast is live.\n\n${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nFull episode on all major podcast platforms.\n\n#GoodNews #Podcast #Wellbeing` },

    // ── Pinterest ─────────────────────────────────────────────
    { typeId: 'pinterest-pin',        platform: 'pinterest', label: 'Pin',
      specs: 'Image · 2:3 ratio', charLimit: 500, charLimitLabel: '500',
      captionFn: (ep, fl) => `${ep.title} — a feel-good episode full of wholesome stories 🌿 #GoodNews #GoodNewsCast #PositiveVibes` },
    { typeId: 'pinterest-video',      platform: 'pinterest', label: 'Video Pin',
      specs: 'MP4 · 2:3 · up to 15 min', charLimit: 500, charLimitLabel: '500',
      captionFn: (ep, fl) => `${ep.title} 🌿 Your weekly good news podcast. #GoodNewsCast #GoodNews #Wholesome` },

    // ── Threads ───────────────────────────────────────────────
    { typeId: 'threads-post',         platform: 'threads',   label: 'Post',
      specs: '500 chars · images/video', charLimit: 500, charLimitLabel: '500',
      captionFn: (ep, fl) => `✨ ${ep.title}${fl ? `\n\n"${fl}"` : ''}\n\nGood news is out there if you know where to look 🌱` },

    // ── Bluesky ───────────────────────────────────────────────
    { typeId: 'bluesky-post',         platform: 'bluesky',   label: 'Post',
      specs: '300 chars · images/video', charLimit: 300, charLimitLabel: '300',
      captionFn: (ep, fl) => `🎙️ ${ep.title}${fl ? ` — "${fl.slice(0, 70)}…"` : ''} #GoodNews` },

    // ── Tumblr ────────────────────────────────────────────────
    { typeId: 'tumblr-post',          platform: 'tumblr',    label: 'Post',
      specs: 'Text + media', charLimit: 4096, charLimitLabel: '4,096',
      captionFn: (ep, fl) => `# ${ep.title}\n\n${fl ? `> "${fl}"\n\n` : ''}Another week, another batch of stories that give us a reason to smile. Follow along for your regular dose of wholesome news 🌿\n\n#good news #goodnewscast #wholesome #positive news` },
];

// =============================================
// SOCIAL ACCOUNTS TAB
// =============================================

function getConnectedAccounts() {
    try { return JSON.parse(localStorage.getItem('gnc_accounts') || '{}'); }
    catch { return {}; }
}

function saveConnectedAccounts(accounts) {
    localStorage.setItem('gnc_accounts', JSON.stringify(accounts));
}

function initSocialAccounts() { /* render on tab open */ }

function renderAccountCards() {
    const grid = document.getElementById('accounts-grid');
    if (!grid) return;
    const accounts = getConnectedAccounts();
    let connectedCount = 0;

    grid.innerHTML = PLATFORMS.map(p => {
        const connected = accounts[p.id];
        if (connected) connectedCount++;
        return `
            <div class="account-card ${connected ? 'connected' : ''}" id="accard-${p.id}">
                <div class="account-card-header">
                    <div class="platform-logo" style="background:rgba(${p.colorRgb},0.12);color:${p.color}">${p.emoji}</div>
                    <div class="account-card-info">
                        <h3>${p.name}</h3>
                        <p id="achandle-${p.id}">${connected ? '@' + connected : 'Not connected'}</p>
                    </div>
                    <div class="platform-status-badge ${connected ? 'connected' : 'disconnected'}">
                        ${connected ? '● Connected' : '○ Off'}
                    </div>
                </div>
                <div class="account-card-specs">
                    <strong>Content Formats</strong>
                    ${PLATFORM_TYPES.filter(t => t.platform === p.id).map(t => t.label).join(' · ')}<br>
                    <em>${p.hint}</em>
                </div>
                <div class="account-card-footer">
                    ${connected
                        ? `<span style="flex:1;font-size:13px;color:var(--text-muted)">@${connected}</span>
                           <button class="btn-platform-connect disconnect" onclick="disconnectPlatform('${p.id}')">Disconnect</button>`
                        : `<input type="text" placeholder="Your @handle or channel name" id="acinput-${p.id}" />
                           <button class="btn-platform-connect connect" onclick="connectPlatform('${p.id}')">Connect</button>`
                    }
                </div>
            </div>`;
    }).join('');

    const countEl = document.getElementById('connected-count');
    if (countEl) countEl.textContent = connectedCount;
}

window.connectPlatform = function(platformId) {
    const input = document.getElementById(`acinput-${platformId}`);
    const handle = input ? input.value.trim().replace(/^@/, '') : '';
    if (!handle) {
        if (input) { input.style.borderColor = 'var(--danger)'; setTimeout(() => { input.style.borderColor = ''; }, 1500); }
        return;
    }
    const accounts = getConnectedAccounts();
    accounts[platformId] = handle;
    saveConnectedAccounts(accounts);
    showToast(`${platformId} connected as @${handle}`);
    renderAccountCards();
    if (document.getElementById('tab-distribute')?.classList.contains('active')) {
        renderPalette(); refreshFlowNodes();
    }
};

window.disconnectPlatform = function(platformId) {
    const accounts = getConnectedAccounts();
    delete accounts[platformId];
    saveConnectedAccounts(accounts);
    // Remove any flow nodes for this platform from current episode
    if (_distEp) {
        _distFlowNodes = _distFlowNodes.filter(id => {
            const pt = PLATFORM_TYPES.find(x => x.typeId === id);
            return pt ? pt.platform !== platformId : true;
        });
        saveFlowNodes(_distEp.id);
    }
    showToast(`${platformId} disconnected`);
    renderAccountCards();
    if (document.getElementById('tab-distribute')?.classList.contains('active')) {
        renderPalette(); renderPlatformNodes(_distEp);
        requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));
    }
};

// =============================================
// DISTRIBUTE TAB
// =============================================

let _distEp         = null;
let _distPlatform   = null;
let _distFlowNodes  = []; // typeIds currently in the flow for selected episode

function getFlowNodes(epId) {
    if (!epId) return [];
    try { return JSON.parse(localStorage.getItem(`gnc_flow_${epId}`) || '[]'); }
    catch { return []; }
}

function saveFlowNodes(epId) {
    if (!epId) return;
    localStorage.setItem(`gnc_flow_${epId}`, JSON.stringify(_distFlowNodes));
}

function getPostStatuses(epId) {
    if (!epId) return {};
    try { return JSON.parse(localStorage.getItem(`gnc_post_${epId}`) || '{}'); }
    catch { return {}; }
}

function savePostStatus(epId, typeId, status) {
    const s = getPostStatuses(epId);
    s[typeId] = status;
    localStorage.setItem(`gnc_post_${epId}`, JSON.stringify(s));
}

function initDistribute() { /* lazy — loads on tab open */ }

function loadDistributeEpisodes() {
    renderPalette();
    const container = document.getElementById('distribute-ep-list');
    if (!container) return;

    fetch(`${API_BASE}/api/episodes`)
        .then(res => res.json())
        .then(episodes => {
            if (episodes.length === 0) {
                container.innerHTML = `<div class="loader" style="padding:16px;font-size:13px;text-align:center">No episodes yet.<br><br>Generate one in<br>Episodes List first.</div>`;
                renderFlowWithEpisode(null);
                return;
            }
            container.innerHTML = episodes.map((ep, idx) => `
                <div class="episode-card ${idx === 0 ? 'active' : ''}" onclick="selectDistributeEp(${ep.id}, this)">
                    <h3 style="font-size:13px">${ep.title}</h3>
                    <span>ID: ${ep.id} · ${ep.status}</span>
                </div>`).join('');
            selectDistributeEp(episodes[0].id, container.querySelector('.episode-card'));
        })
        .catch(() => {
            container.innerHTML = `<div class="loader" style="color:var(--danger);padding:16px;font-size:13px">Backend offline.</div>`;
            renderFlowWithEpisode({ id: null, title: 'Demo Episode', status: 'video_ready', script_json: '[]' });
        });
}

window.selectDistributeEp = function(epId, element) {
    document.querySelectorAll('#distribute-ep-list .episode-card').forEach(c => c.classList.remove('active'));
    if (element) element.classList.add('active');

    fetch(`${API_BASE}/api/episodes/${epId}`)
        .then(res => res.json())
        .then(ep => { _distEp = ep; _distFlowNodes = getFlowNodes(ep.id); renderFlowWithEpisode(ep); })
        .catch(() => {
            _distEp = { id: epId, title: 'Episode ' + epId, status: 'video_ready', script_json: '[]' };
            _distFlowNodes = getFlowNodes(epId);
            renderFlowWithEpisode(_distEp);
        });
};

function renderFlowWithEpisode(ep) {
    const titleEl = document.getElementById('flow-source-title');
    const metaEl  = document.getElementById('flow-source-meta');
    if (!ep) {
        if (titleEl) titleEl.textContent = 'No episode selected';
        if (metaEl)  metaEl.textContent  = 'Select an episode from the left';
    } else {
        if (titleEl) titleEl.textContent = ep.title || 'Episode';
        if (metaEl)  metaEl.textContent  = `Status: ${ep.status || '—'} · ID: ${ep.id || '—'}`;
    }

    renderPlatformNodes(ep);
    _distPlatform = null;

    const panel = document.getElementById('platform-panel');
    if (panel) panel.innerHTML = `
        <div class="panel-empty">
            <span>☝️</span>
            <p>Click a platform node above to craft its content</p>
        </div>`;

    renderPalette();
    requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));
}

// ── Palette ──────────────────────────────────────────────────

function renderPalette() {
    const container = document.getElementById('palette-chips');
    if (!container) return;
    const accounts  = getConnectedAccounts();

    // Count connected platforms for header note
    const connCount = PLATFORMS.filter(p => accounts[p.id]).length;
    const noteEl = document.getElementById('palette-conn-note');
    if (noteEl) noteEl.textContent = connCount < PLATFORMS.length
        ? `${PLATFORMS.length - connCount} platform${PLATFORMS.length - connCount !== 1 ? 's' : ''} not connected — go to Social Accounts`
        : '✓ All platforms connected';

    container.innerHTML = PLATFORMS.map(p => {
        const connected = !!accounts[p.id];
        const types     = PLATFORM_TYPES.filter(t => t.platform === p.id);

        return `
            <div class="palette-row">
                <div class="palette-platform-icon"
                     style="background:rgba(${p.colorRgb},0.12);color:${p.color};${connected ? '' : 'opacity:0.35'}">
                    ${p.emoji}
                </div>
                <div class="palette-chips-group">
                    ${types.map(pt => {
                        const inFlow   = _distFlowNodes.includes(pt.typeId);
                        const disabled = !connected;
                        const cls      = disabled ? 'palette-chip palette-chip-disabled'
                                       : inFlow    ? 'palette-chip palette-chip-in-flow'
                                       :             'palette-chip';
                        const style    = `border-color:${connected ? p.color : 'transparent'};color:${connected ? p.color : 'var(--text-muted)'}`;
                        const drag     = connected && !inFlow ? 'true' : 'false';
                        const onStart  = connected && !inFlow ? `handleDragStart(event,'${pt.typeId}')` : '';
                        const onClick  = disabled ? `showConnectHint('${p.id}')` : '';
                        return `<div class="${cls}" style="${style}"
                                     draggable="${drag}"
                                     ondragstart="${onStart}"
                                     onclick="${onClick}"
                                     title="${p.name} ${pt.label} · ${pt.specs}">
                                    ${pt.label}
                                </div>`;
                    }).join('')}
                </div>
            </div>`;
    }).join('');
}

// ── Drag & Drop ───────────────────────────────────────────────

window.handleDragStart = function(event, typeId) {
    event.dataTransfer.setData('text/plain', typeId);
    event.dataTransfer.effectAllowed = 'copy';
};

window.handleDragOver = function(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    document.getElementById('flow-canvas')?.classList.add('drag-over');
};

window.handleDragLeave = function(event) {
    // Only remove if truly leaving the canvas (not entering a child)
    const canvas = document.getElementById('flow-canvas');
    if (canvas && !canvas.contains(event.relatedTarget)) {
        canvas.classList.remove('drag-over');
    }
};

window.handleFlowDrop = function(event) {
    event.preventDefault();
    document.getElementById('flow-canvas')?.classList.remove('drag-over');
    if (!_distEp) { showToast('Select an episode first'); return; }

    const typeId = event.dataTransfer.getData('text/plain');
    if (!typeId) return;
    const pt = PLATFORM_TYPES.find(x => x.typeId === typeId);
    if (!pt) return;

    if (_distFlowNodes.includes(typeId)) {
        showToast(`${pt.label} already in flow`); return;
    }
    _distFlowNodes.push(typeId);
    saveFlowNodes(_distEp.id);
    renderPlatformNodes(_distEp);
    renderPalette();
    requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));
};

window.removeFlowNode = function(typeId) {
    _distFlowNodes = _distFlowNodes.filter(id => id !== typeId);
    if (_distEp) saveFlowNodes(_distEp.id);
    if (_distPlatform === typeId) {
        _distPlatform = null;
        const panel = document.getElementById('platform-panel');
        if (panel) panel.innerHTML = `<div class="panel-empty"><span>☝️</span><p>Click a platform node to craft its content</p></div>`;
    }
    renderPlatformNodes(_distEp);
    renderPalette();
    requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));
};

// ── Flow nodes ────────────────────────────────────────────────

function renderPlatformNodes(ep) {
    const row = document.getElementById('flow-platform-row');
    if (!row) return;
    const postStatuses = ep ? getPostStatuses(ep.id) : {};

    if (_distFlowNodes.length === 0) {
        row.innerHTML = `<div class="flow-drop-hint">Drag platforms from above to build your distribution flow</div>`;
        return;
    }

    row.innerHTML = _distFlowNodes.map(typeId => {
        const pt  = PLATFORM_TYPES.find(x => x.typeId === typeId);
        if (!pt) return '';
        const p   = PLATFORMS.find(x => x.id === pt.platform);
        if (!p) return '';
        const status      = postStatuses[typeId] || 'draft';
        const statusLabel = status.charAt(0).toUpperCase() + status.slice(1);
        const isActive    = _distPlatform === typeId;

        return `
            <div class="platform-node ${isActive ? 'active' : ''}"
                 id="pnode-${typeId}"
                 style="border-color:${p.color}"
                 onclick="selectPlatformNode('${typeId}')">
                <div class="platform-node-icon" style="background:rgba(${p.colorRgb},0.12);color:${p.color}">${p.emoji}</div>
                <div class="platform-node-name">${p.name}</div>
                <div class="platform-node-type">${pt.label}</div>
                <div class="platform-node-status pns-${status}">${statusLabel}</div>
                <button class="node-remove-btn" onclick="event.stopPropagation();removeFlowNode('${typeId}')">×</button>
            </div>`;
    }).join('');
}

function drawFlowLines() {
    const svg    = document.getElementById('flow-svg');
    const src    = document.getElementById('flow-source-node');
    const canvas = document.getElementById('flow-canvas');
    if (!svg || !src || !canvas) return;

    const cr = canvas.getBoundingClientRect();
    const sr = src.getBoundingClientRect();
    const sx = sr.left + sr.width  / 2 - cr.left;
    const sy = sr.bottom - cr.top;

    let paths = '';
    document.querySelectorAll('.platform-node').forEach(node => {
        const nr  = node.getBoundingClientRect();
        const ex  = nr.left + nr.width  / 2 - cr.left;
        const ey  = nr.top  - cr.top;
        const mid = (sy + ey) / 2;
        const isActive = node.classList.contains('active');
        const stroke   = isActive ? 'rgba(129,140,248,0.7)' : 'rgba(129,140,248,0.35)';

        paths += `<path d="M ${sx} ${sy} C ${sx} ${mid}, ${ex} ${mid}, ${ex} ${ey}"
                       stroke="${stroke}" stroke-width="${isActive ? 2 : 1.5}" fill="none" stroke-linecap="round"/>`;
    });
    svg.innerHTML = paths;
}

function refreshFlowNodes() {
    renderPlatformNodes(_distEp);
    requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));
}

// ── Platform Panel ────────────────────────────────────────────

window.selectPlatformNode = function(typeId) {
    const pt = PLATFORM_TYPES.find(x => x.typeId === typeId);
    if (!pt || !_distEp) return;
    const p = PLATFORMS.find(x => x.id === pt.platform);
    if (!p) return;

    _distPlatform = typeId;
    document.querySelectorAll('.platform-node').forEach(n => n.classList.remove('active'));
    const node = document.getElementById(`pnode-${typeId}`);
    if (node) node.classList.add('active');
    requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));

    const panel    = document.getElementById('platform-panel');
    const isPosted = getPostStatuses(_distEp.id)[typeId] === 'posted';

    panel.innerHTML = `
        <div class="panel-header">
            <div class="panel-platform-logo" style="background:rgba(${p.colorRgb},0.12);color:${p.color}">${p.emoji}</div>
            <div>
                <div class="panel-platform-name">${p.name} — ${pt.label}</div>
                <div class="panel-platform-specs">${pt.specs} · ${pt.charLimitLabel} chars</div>
            </div>
        </div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:14px">✨ Crafting caption from episode script...</div>
        <div class="panel-caption-label"><span>Caption / Copy</span></div>
        <textarea class="panel-caption-area generating" rows="5" placeholder="Generating..."></textarea>`;

    setTimeout(() => {
        let firstLine = '';
        try {
            const script = JSON.parse(_distEp.script_json || '[]');
            if (script.length > 0) firstLine = script[0].text || '';
        } catch {}

        const caption = pt.captionFn(_distEp, firstLine);

        panel.innerHTML = `
            <div class="panel-header">
                <div class="panel-platform-logo" style="background:rgba(${p.colorRgb},0.12);color:${p.color}">${p.emoji}</div>
                <div>
                    <div class="panel-platform-name">${p.name} — ${pt.label}</div>
                    <div class="panel-platform-specs">${pt.specs} · ${pt.charLimitLabel} chars max</div>
                </div>
            </div>
            <button class="btn-regenerate" onclick="selectPlatformNode('${typeId}')">↺ Regenerate</button>
            <div class="panel-caption-label">
                <span>Caption / Copy</span>
                <span class="panel-char-count" id="char-count-display">0 / ${pt.charLimit.toLocaleString()}</span>
            </div>
            <textarea class="panel-caption-area" id="panel-caption-text" rows="6"
                      oninput="updateCharCount(${pt.charLimit})">${caption}</textarea>
            ${isPosted
                ? `<div class="post-status-badge posted">✓ Posted to ${p.name} (${pt.label})</div>`
                : `<div class="panel-actions">
                       <button class="btn-post-now"
                               style="background:${p.color};color:${p.color === '#e7e9ea' || p.color === '#aaaaaa' ? '#000' : '#fff'}"
                               onclick="postToPlatform('${typeId}')">Post to ${p.name}</button>
                       <button class="btn-schedule" onclick="schedulePlatformPost('${typeId}')">📅 Schedule</button>
                   </div>`
            }`;

        updateCharCount(pt.charLimit);
    }, 900);
};

window.showConnectHint = function(platformId) {
    const p = PLATFORMS.find(x => x.id === platformId);
    showToast(`Connect ${p ? p.name : platformId} in Social Accounts first`);
};

window.updateCharCount = function(limit) {
    const ta = document.getElementById('panel-caption-text');
    const el = document.getElementById('char-count-display');
    if (!ta || !el) return;
    const len = ta.value.length;
    el.textContent = `${len.toLocaleString()} / ${limit.toLocaleString()}`;
    el.style.color  = len > limit ? 'var(--danger)' : 'var(--text-muted)';
};

window.postToPlatform = function(typeId) {
    const pt = PLATFORM_TYPES.find(x => x.typeId === typeId);
    const p  = pt ? PLATFORMS.find(x => x.id === pt.platform) : null;
    if (!pt || !p || !_distEp) return;

    showToast(`Queuing post to ${p.name} (${pt.label})...`);
    savePostStatus(_distEp.id, typeId, 'queued');

    const node = document.getElementById(`pnode-${typeId}`);
    if (node) {
        const s = node.querySelector('.platform-node-status');
        if (s) { s.className = 'platform-node-status pns-queued'; s.textContent = 'Queued'; }
    }

    setTimeout(() => {
        savePostStatus(_distEp.id, typeId, 'posted');
        showToast(`✓ Posted to ${p.name} (${pt.label})!`);
        renderPlatformNodes(_distEp);
        requestAnimationFrame(() => requestAnimationFrame(drawFlowLines));
        selectPlatformNode(typeId);
    }, 2000);
};

window.schedulePlatformPost = function(typeId) {
    const pt = PLATFORM_TYPES.find(x => x.typeId === typeId);
    const p  = pt ? PLATFORMS.find(x => x.id === pt.platform) : null;
    showToast(`Scheduling for ${p ? p.name : typeId} (${pt ? pt.label : ''}) — coming soon!`);
};

window.addEventListener('resize', () => {
    if (document.getElementById('tab-distribute')?.classList.contains('active')) {
        requestAnimationFrame(drawFlowLines);
    }
});

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
