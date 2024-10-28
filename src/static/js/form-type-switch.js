document.addEventListener("DOMContentLoaded", function () {
  const fields = {
    mediaType: document.getElementById("id_media_type"),
    parentTV: document.getElementById("id_parent_tv"),
    parentSeason: document.getElementById("id_parent_season"),
    seasonNumber: document.getElementById("id_season_number"),
    episodeNumber: document.getElementById("id_episode_number")
  };

  const fieldVisibility = {
    season: {
      parentTV: true,
      parentSeason: false,
      seasonNumber: true,
      episodeNumber: false
    },
    episode: {
      parentTV: false,
      parentSeason: true,
      seasonNumber: true,
      episodeNumber: true
    },
    default: {
      parentTV: false,
      parentSeason: false,
      seasonNumber: false,
      episodeNumber: false
    }
  };

  function updateFieldVisibility() {
    const selectedMediaType = fields.mediaType.value;
    const visibility = fieldVisibility[selectedMediaType] || fieldVisibility.default;

    for (const [field, isVisible] of Object.entries(visibility)) {
      const element = fields[field];
      element.parentNode.style.display = isVisible ? "block" : "none";
      element.required = isVisible;
    }
  }

  fields.mediaType.addEventListener("change", updateFieldVisibility);
  updateFieldVisibility(); // Set initial state
});