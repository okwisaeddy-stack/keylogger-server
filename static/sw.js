self.addEventListener('push', function(e) {
  const data = e.data ? e.data.text() : 'New alert';
  e.waitUntil(
    self.registration.showNotification('Keylogger Alert', {
      body: data,
      vibrate: [200, 100, 200]
    })
  );
});
