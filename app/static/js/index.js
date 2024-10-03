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
  const searchQuery = document.querySelector('input[name="query"]').value.trim().toLowerCase();
  if (searchQuery) {
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
}, false);
