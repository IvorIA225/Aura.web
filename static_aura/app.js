document.addEventListener('DOMContentLoaded', () => {
    const moodScreen = document.getElementById('mood-screen');
    const chatScreen = document.getElementById('chat-screen');
    const moodBtns = document.querySelectorAll('.mood-btn');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const micBtn = document.getElementById('mic-btn');
    const typingIndicator = document.getElementById('typing-indicator');
    const prenomInput = document.getElementById('prenom-input');
    const voiceEnabledCb = document.getElementById('voice-enabled');
    const auraAudio = document.getElementById('aura-audio');
    const loginBtn = document.getElementById('login-btn');
    const loginError = document.getElementById('login-error');
    const moodSection = document.getElementById('mood-section');

    // Sidebar Elements
    const sidebarUserName = document.getElementById('sidebar-user-name');
    const headerUserPrenom = document.getElementById('header-user-prenom');
    const sidebarVoiceEnabled = document.getElementById('sidebar-voice-enabled');
    const voiceStyleSelect = document.getElementById('voice-style');
    const newSessionBtn = document.getElementById('new-session-btn');
    const clearHistoryBtn = document.getElementById('clear-history-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const agentGenderLogin = document.getElementById('agent-gender-login');
    const agentGenderSidebar = document.getElementById('agent-gender-sidebar');

    let userId = null;
    let prenom = null;
    let currentMood = null;
    let isTyping = false;

    if (typeof marked !== 'undefined') {
        marked.setOptions({ breaks: true, gfm: true });
    }

    // Synchronize Voice Checkboxes
    voiceEnabledCb.addEventListener('change', (e) => {
        sidebarVoiceEnabled.checked = e.target.checked;
    });
    sidebarVoiceEnabled.addEventListener('change', (e) => {
        voiceEnabledCb.checked = e.target.checked;
    });


    // Synchronize Gender Selects
    agentGenderLogin.addEventListener('change', (e) => {
        agentGenderSidebar.value = e.target.value;
    });
    agentGenderSidebar.addEventListener('change', (e) => {
        agentGenderLogin.value = e.target.value;
    });

    // --- Login Button: validate fields then reveal mood section ---
    function showLoginError(msg) {
        loginError.textContent = msg;
        loginError.classList.remove('hidden');
        loginError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    loginBtn.addEventListener('click', () => {
        const pName = prenomInput.value.trim();
        const pPin = document.getElementById('pin-input').value.trim();
        loginError.classList.add('hidden');

        if (!pName || pName.length < 2) {
            showLoginError("✨ Entre ton prénom (au moins 2 caractères) avant de continuer.");
            prenomInput.focus();
            return;
        }
        if (!pPin || !/^\d{5}$/.test(pPin)) {
            showLoginError("🔐 Entre un code secret à exactement 5 chiffres.");
            document.getElementById('pin-input').focus();
            return;
        }

        // All good — reveal mood section
        loginBtn.classList.add('hidden');
        moodSection.classList.remove('hidden');
    });

    // Also allow Enter key on PIN field to trigger login
    document.getElementById('pin-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') loginBtn.click();
    });

    moodBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const pName = prenomInput.value.trim();
            const pPin = document.getElementById('pin-input').value.trim();
            // Fields already validated by loginBtn — just start session
            prenom = pName;
            currentMood = btn.dataset.mood;
            startSession(pPin);
        });
    });

    function getGreeting() {
        const hour = new Date().getHours();
        return (hour >= 5 && hour < 18) ? "Bonjour" : "Bonsoir";
    }

    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        if(this.value.trim() === '') {
            this.style.height = 'auto';
        }
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    // Microphone / Voice Note Logic
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    micBtn.addEventListener('click', async () => {
        if (!isRecording) {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = e => {
                    if (e.data.size > 0) audioChunks.push(e.data);
                };
                
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    await processAudioInput(audioBlob);
                };
                
                mediaRecorder.start();
                isRecording = true;
                micBtn.classList.add('recording');
                chatInput.placeholder = "Enregistrement en cours...";
            } catch (err) {
                console.error("Microphone access denied", err);
                alert("Accès au microphone refusé.");
            }
        } else {
            mediaRecorder.stop();
            isRecording = false;
            micBtn.classList.remove('recording');
            chatInput.placeholder = "Écris ton message ici...";
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
        }
    });

    async function processAudioInput(blob) {
        showTypingIndicator();
        const formData = new FormData();
        formData.append("file", blob, "voice_note.webm");
        
        try {
            const res = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });
            if (!res.ok) throw new Error("Erreur transcription");
            const data = await res.json();
            
            if (data.text && data.text.trim().length > 0) {
                chatInput.value = data.text;
                hideTypingIndicator();
                sendMessage(); // Send automatically
            } else {
                hideTypingIndicator();
                alert("Je n'ai pas bien entendu, peux-tu répéter ?");
            }
        } catch(err) {
            console.error(err);
            hideTypingIndicator();
            alert("Erreur lors de l'analyse vocale.");
        }
    }

    // Sidebar Actions
    logoutBtn.addEventListener('click', () => {
        if(confirm("Veux-tu te déconnecter et revenir à l'accueil ?")) {
            resetApp();
        }
    });

    newSessionBtn.addEventListener('click', () => {
        if(confirm("Commencer une nouvelle discussion ?")) {
            // Keep user, just clear UI
            clearChatUI();
            addMessage(`Bonjour ${prenom} ! Nouvelle discussion. De quoi aimerais-tu parler ?`, 'bot', false);
        }
    });

    clearHistoryBtn.addEventListener('click', async () => {
        if(confirm("Veux-tu vraiment effacer tout ton historique avec Aura ? (Cette action est irréversible)")) {
            try {
                await fetch(`/api/history/${userId}`, { method: 'DELETE' });
                clearChatUI();
                addMessage(`Ton historique a été effacé avec succès. On recommence à zéro. ✨`, 'bot', false);
            } catch(e) {
                alert("Erreur lors de la suppression de l'historique.");
            }
        }
    });

    async function startSession(pinCode) {
        moodScreen.classList.remove('active');
        chatScreen.classList.add('active');
        showTypingIndicator();
        
        try {
            const res = await fetch('/api/session/start', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prenom: prenom,
                    pin: pinCode,
                    mood: currentMood,
                    agent_gender: agentGenderLogin.value
                })
            });
            
            if(!res.ok) {
                const err = await res.json();
                throw new Error(err.detail);
            }
            
            const data = await res.json();
            userId = data.user_id;
            prenom = data.prenom; // capitalisé par le backend

            // Update UI
            sidebarUserName.textContent = prenom;
            headerUserPrenom.textContent = "👤 " + prenom;

            hideTypingIndicator();

            // Si c'est un retour et qu'il y a un historique
            if (data.historique && data.historique.length > 0) {
                data.historique.forEach(msg => {
                    addMessage(msg.content, msg.role === 'assistant' ? 'bot' : 'user', msg.role === 'assistant');
                });
                
                const retourMsg = agentGenderLogin.value === 'feminine'
                    ? `Contente de te revoir, ${prenom} ! On reprend là où on s'était arrêtées ? ✨`
                    : `Content de te revoir, ${prenom} ! On reprend là où on s'était arrêtés ? ✨`;
                addMessage(retourMsg, 'bot', false);
            } else if (data.welcome_msg) {
                // Nouvelle conversation via LLM
                addMessage(data.welcome_msg, 'bot', true);
            }

        } catch (error) {
            hideTypingIndicator();
            console.error(error);
            alert("Erreur: " + error.message);
            resetApp();
        }
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isTyping || !userId) return;

        chatInput.value = '';
        chatInput.style.height = 'auto';
        chatInput.focus();
        
        addMessage(text, 'user', false);
        showTypingIndicator();

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    prenom: prenom,
                    message: text,
                    mood: currentMood,
                    voice_enabled: sidebarVoiceEnabled.checked,
                    voice_style: voiceStyleSelect.value,
                    agent_gender: agentGenderSidebar.value
                })
            });

            if(!res.ok) {
                const errorData = await res.json();
                throw new Error(errorData.detail || "Erreur serveur");
            }

            const data = await res.json();
            currentMood = null; // Seulement pour le premier message
            
            hideTypingIndicator();
            addMessage(data.response, 'bot', true);

            // Jouer l'audio si fourni
            if (data.audio) {
                auraAudio.src = data.audio;
                auraAudio.play().catch(e => console.log("Auto-play bloqué par le navigateur", e));
            }

        } catch (error) {
            hideTypingIndicator();
            addMessage("Pardon, j'ai rencontré un petit problème technique (Vérifie ta clé Groq). Peux-tu répéter ?", 'bot');
            console.error("Chat error:", error);
        }
    }

    function addMessage(text, sender, parseMarkdown = false) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message', sender);
        
        if (parseMarkdown && typeof marked !== 'undefined') {
            msgDiv.innerHTML = marked.parse(text);
        } else {
            msgDiv.textContent = text;
        }
        
        chatMessages.insertBefore(msgDiv, typingIndicator);
        scrollToBottom();
    }

    function showTypingIndicator() {
        isTyping = true;
        typingIndicator.classList.remove('hidden');
        scrollToBottom();
    }

    function hideTypingIndicator() {
        isTyping = false;
        typingIndicator.classList.add('hidden');
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function clearChatUI() {
        Array.from(chatMessages.children).forEach(child => {
            if (child.id !== 'typing-indicator' && !child.classList.contains('disclaimer')) {
                child.remove();
            }
        });
    }

    function resetApp() {
        userId = null;
        currentMood = null;
        clearChatUI();
        chatScreen.classList.remove('active');
        moodScreen.classList.add('active');
        // Reset login form state
        loginBtn.classList.remove('hidden');
        moodSection.classList.add('hidden');
        loginError.classList.add('hidden');
        prenomInput.value = '';
        document.getElementById('pin-input').value = '';
    }
});
