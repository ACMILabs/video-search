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
  var isSafariMac = /Safari/.test(navigator.userAgent) &&
                  !/Mobile/.test(navigator.userAgent) &&
                  /Apple Computer/.test(navigator.vendor);

  const select = document.getElementsByTagName('select')[0];
  if (isSafariMac && select) {
    select.classList.add('macos-safari');
  }
}, false);
