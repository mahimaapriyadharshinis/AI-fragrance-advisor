document.addEventListener('DOMContentLoaded', () => {
    const advisorForm = document.getElementById('advisorForm');
    const userInput = document.getElementById('userInput');
    const chatHistory = document.getElementById('chatHistory');
    const landingView = document.getElementById('landingView');
    const quickPromptsContainer = document.getElementById('quickPromptsContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const recommendationsSection = document.getElementById('recommendationsSection');
    const productsGrid = document.getElementById('productsGrid');
    const infoBtn = document.getElementById('infoBtn');

    // Maintain running conversational memory history locally in frontend session
    let conversationHistory = [];

    // Attach click events to the quick-prompt pills
    document.querySelectorAll('.prompt-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const promptText = pill.getAttribute('data-prompt');
            userInput.value = promptText;
            submitQuery(promptText);
        });
    });

    advisorForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = userInput.value.trim();
        if (query) {
            submitQuery(query);
        }
    });

    infoBtn.addEventListener('click', () => {
        alert("AI Scent Advisor: Designed to match your personality & preferences with our luxury fragrance database using advanced Sarvam AI LLM capabilities.");
    });

    async function submitQuery(query) {
        // Clear input field
        userInput.value = '';

        // Hide landing layout features & quick prompts on first query to transform into chat mode
        landingView.classList.add('hidden');
        quickPromptsContainer.classList.add('hidden');

        // Show conversational dialogue block
        chatHistory.classList.remove('hidden');

        // Render user message bubble
        appendChatBubble(query, 'user');

        // Prepare and show loader
        loadingIndicator.classList.remove('hidden');
        recommendationsSection.classList.add('hidden');
        productsGrid.innerHTML = '';

        try {
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: query,
                    history: conversationHistory
                })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server returned status: ${response.status}`);
            }

            const data = await response.json();
            
            // Render Bot response dialogue
            appendChatBubble(data.bot_reply, 'bot');

            // Save this exchange in memory
            conversationHistory.push({role: "user", content: query});
            conversationHistory.push({role: "assistant", content: data.bot_reply});

            // Render matching recommended product cards if returned
            if (data.recommended_products && data.recommended_products.length > 0) {
                renderProducts(data.recommended_products);
                recommendationsSection.classList.remove('hidden');
                
                // Clear history to restart a new recommendation flow next time
                conversationHistory = [];
            }

        } catch (error) {
            console.error('Error fetching chat response:', error);
            appendChatBubble(`My apologies. I encountered an issue connecting to the perfume directory server. Detail: ${error.message}`, 'bot');
        } finally {
            loadingIndicator.classList.add('hidden');
            // Auto scroll to bottom
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }
    }

    function appendChatBubble(text, sender) {
        const bubbleContainer = document.createElement('div');
        bubbleContainer.style.display = 'flex';
        bubbleContainer.style.flexDirection = 'column';
        bubbleContainer.style.gap = '8px';
        bubbleContainer.style.alignItems = sender === 'user' ? 'flex-end' : 'flex-start';
        bubbleContainer.style.width = '100%';

        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${sender}`;
        
        if (sender === 'bot') {
            // Find option brackets like [Delicious fruits]
            const optionRegex = /\[(.*?)\]/g;
            let options = [];
            let match;
            while ((match = optionRegex.exec(text)) !== null) {
                options.push(match[1]);
            }
            
            // Clean text of brackets
            let cleanText = text.replace(optionRegex, '').trim();
            cleanText = cleanText
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\*(.*?)\*/g, '<em>$1</em>')
                .replace(/###\s*(.*?)/g, '<h4>$1</h4>')
                .replace(/---\s*/g, '<hr style="border: 0; height: 1px; background: rgba(0,0,0,0.06); margin: 16px 0;">')
                .replace(/\n/g, '<br>');
            
            bubble.innerHTML = cleanText;
            bubbleContainer.appendChild(bubble);

            // If options were extracted, render them as custom suggestion pills
            if (options.length > 0) {
                const optionsRow = document.createElement('div');
                optionsRow.style.display = 'flex';
                optionsRow.style.gap = '8px';
                optionsRow.style.flexWrap = 'wrap';
                optionsRow.style.marginTop = '4px';

                options.forEach(opt => {
                    const btn = document.createElement('button');
                    btn.className = 'prompt-pill';
                    btn.style.padding = '8px 16px';
                    btn.style.fontSize = '0.9rem';
                    btn.style.margin = '0';
                    btn.textContent = opt;
                    btn.addEventListener('click', () => {
                        // Click to submit the text
                        userInput.value = opt;
                        submitQuery(opt);
                    });
                    optionsRow.appendChild(btn);
                });
                bubbleContainer.appendChild(optionsRow);
            }
        } else {
            bubble.textContent = text;
            bubbleContainer.appendChild(bubble);
        }
        
        chatHistory.appendChild(bubbleContainer);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function renderProducts(products) {
        products.forEach(product => {
            const card = document.createElement('div');
            card.className = 'product-card';

            const ratingStars = '★'.repeat(Math.round(product.rating)) + '☆'.repeat(5 - Math.round(product.rating));

            card.innerHTML = `
                <div class="product-name">${product.name}</div>
                <div class="product-rating">
                    <span class="star">${ratingStars}</span>
                    <span>(${product.rating})</span>
                </div>
                <div class="product-desc">${product.description}</div>
            `;
            productsGrid.appendChild(card);
        });
    }
});
