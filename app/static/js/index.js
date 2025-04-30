function setPlaybackTime(videoId, seconds) {
  // Stop all other videos playing
  const videos = document.getElementsByTagName('video');
  for (let index = 0; index < videos.length; index++) {
    const element = videos[index];
    element.pause();
  }

  // Jump to time
  const video = document.getElementById(`video-${videoId}`);
  video.currentTime = seconds - 0.3;
  video.play();
}

document.addEventListener('DOMContentLoaded', function() {
  // Highlight query strings in search results
  let searchQuery = document.querySelector('input[name="query"]');
  if (searchQuery) {
    searchQuery = searchQuery.value.trim().toLowerCase();
    const segments = document.querySelectorAll('.segment dd');
    segments.forEach(segment => {
      const textContent = segment.innerHTML;
      if (textContent.toLowerCase().includes(searchQuery)) {
        // Create a regex to match the search query (case-insensitive)
        const regex = new RegExp(`(${searchQuery})`, 'gi');
        const highlightedText = textContent.replace(regex, '<span class="highlight">$1</span>');
        segment.innerHTML = highlightedText;
      }
    });
  }

  const video   = document.getElementById('supercut');
  const credits = Array.from(
    /** @type {NodeListOf<HTMLLIElement>} */
    document.querySelectorAll('.supercut-credits li')
  );

  if (!video || credits.length === 0) return;

  /* Turn per-clip durations into absolute start / end */
  let totalRunningTime = 0;
  credits.forEach(li => {
    const duration = parseFloat(li.dataset.duration) || 0;
    li.dataset.start = totalRunningTime;
    totalRunningTime += duration;
    li.dataset.end   = totalRunningTime;
  });

  /* Show only the credit that matches currentTime */
  function updateCredits() {
    const now = video.currentTime;
    for (const li of credits) {
      const start = parseFloat(li.dataset.start);
      const end = parseFloat(li.dataset.end);
      li.style.display = (now >= start && now < end) ? 'list-item' : 'none';
    }
  }

  video.addEventListener('timeupdate',   updateCredits); // normal playback
  video.addEventListener('seeked',       updateCredits); // user drags scrubber
  video.addEventListener('loadedmetadata', updateCredits); // initial state
}, false);
