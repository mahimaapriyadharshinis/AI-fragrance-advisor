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
    const resetBtn = document.getElementById('resetBtn');
 
    // Maintain running conversational memory history locally in frontend session
    let conversationHistory = [];
    let activeRecommendations = [];
    let activeOtherRecommendations = [];
    let activeDislikedPerfumes = [];
    let activeBrandFilter = null;
    let activeSortByBest = false;
    let activeUserTurns = 0;
    let isSubmitting = false;
 
    // Attach click events to the quick-prompt pills
    document.querySelectorAll('.prompts-grid .prompt-pill').forEach(pill => {
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

    // Reset button clears history and returns to the fresh landing screen
    resetBtn.addEventListener('click', () => {
        conversationHistory = [];
        activeRecommendations = [];
        activeOtherRecommendations = [];
        activeDislikedPerfumes = [];
        activeBrandFilter = null;
        activeSortByBest = false;
        activeUserTurns = 0;
        userInput.value = '';
        
        // Restore landing layout
        landingView.classList.remove('hidden');
        quickPromptsContainer.classList.remove('hidden');
        chatHistory.classList.add('hidden');
        resetBtn.style.display = 'none';
        recommendationsSection.classList.add('hidden');
        productsGrid.innerHTML = '';
        
        // Keep only the first welcome message bubble in chat history
        chatHistory.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 8px; align-items: flex-start; width: 100%;">
                <div class="chat-bubble bot">Welcome! Let us guide you to your perfect fragrance match. Tell us about your preferred scent notes, the vibe you want to create, or the occasion, and our AI Scent Advisor will find the perfect match tailored just for you.</div>
            </div>
        `;
    });
 
    async function submitQuery(query) {
        if (isSubmitting) return;
        isSubmitting = true;
        
        // Clear input field
        userInput.value = '';
 
        // Hide landing layout features & quick prompts on first query to transform into chat mode
        landingView.classList.add('hidden');
        quickPromptsContainer.classList.add('hidden');
 
        // Show conversational dialogue block and reset button
        chatHistory.classList.remove('hidden');
        resetBtn.style.display = 'block';
 
        // Render user message bubble
        appendChatBubble(query, 'user');
 
        // Disable and fade out previous interactive suggestion pills in chat logs
        document.querySelectorAll('.chat-history .prompt-pill').forEach(btn => {
            btn.style.pointerEvents = 'none';
            btn.style.opacity = '0.5';
        });
 
        // Prepare and show loader
        loadingIndicator.classList.remove('hidden');
 
        try {
            const response = await fetch('/api/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: query,
                    history: conversationHistory,
                    recommended_perfumes: activeRecommendations,
                    other_perfumes: activeOtherRecommendations,
                    brand_filter: activeBrandFilter,
                    disliked_perfumes: activeDislikedPerfumes,
                    sort_by_best: activeSortByBest,
                    user_turns: activeUserTurns
                })
            });
 
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.error || `Server returned status: ${response.status}`);
            }
 
            const data = await response.json();
            
            // Render Bot response dialogue
            const replies = data.bot_reply.split('[NEXT_MESSAGE]');
            replies.forEach(reply => {
                if (reply.trim()) {
                    appendChatBubble(reply.trim(), 'bot');
                }
            });
 
            // Save this exchange in memory
            if (data.clear_history) {
                conversationHistory = [];
            }
            conversationHistory.push({role: "user", content: query});
            conversationHistory.push({role: "assistant", content: data.bot_reply});
 
            // Render matching recommended product cards if returned
            if (data.recommended_products && data.recommended_products.length > 0) {
                activeRecommendations = data.recommended_products;
                activeOtherRecommendations = data.other_products || [];
                renderProducts(data.recommended_products);
                recommendationsSection.classList.remove('hidden');
            } else if (activeRecommendations.length > 0) {
                // Keep showing the active recommendations during follow-ups/Q&A
                renderProducts(activeRecommendations);
                recommendationsSection.classList.remove('hidden');
            } else {
                recommendationsSection.classList.add('hidden');
            }
            activeDislikedPerfumes = data.disliked_perfumes || [];
            activeBrandFilter = data.brand_filter || null;
            activeSortByBest = data.sort_by_best || false;
            activeUserTurns = data.user_turns || 0;
 
        } catch (error) {
            console.error('Error fetching chat response:', error);
            appendChatBubble(`My apologies. I encountered an issue connecting to the perfume directory server. Detail: ${error.message}`, 'bot');
        } finally {
            isSubmitting = false;
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
                if (match[1] && match[1].trim()) {
                    options.push(match[1].trim());
                }
            }
            
            // Clean text of brackets
            let cleanText = text.replace(optionRegex, '').trim();
            if (!cleanText && options.length > 0) {
                cleanText = "Here are some notes and accords you can choose from:";
            }
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
        productsGrid.innerHTML = ''; // Clear the grid to avoid duplication
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
