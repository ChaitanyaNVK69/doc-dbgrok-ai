function startVoiceRecognition() {
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'en-US';
    recognition.onresult = (event) => {
        const command = event.results[0][0].transcript;
        fetch('/api/voice_command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('voice-output').textContent = data.response;
        })
        .catch(error => {
            console.error('Error processing voice command:', error);
            document.getElementById('voice-output').textContent = 'Error processing command';
        });
    };
    recognition.onerror = (event) => {
        document.getElementById('voice-output').textContent = 'Voice recognition error: ' + event.error;
    };
    recognition.start();
}