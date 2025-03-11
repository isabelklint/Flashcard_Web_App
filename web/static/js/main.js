// web/static/js/main.js

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is logged in
    checkAuthStatus();
    
    // Get the form element
    const uploadForm = document.querySelector('form[action="/api/presentations/"]');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleFormSubmit);
    }
    
    // Load presentations if the user is authenticated
    loadPresentations();
});

// Check authentication status
function checkAuthStatus() {
    fetch('/auth/status')
        .then(response => response.json())
        .then(data => {
            if (data.authenticated) {
                // Show user info if we have it
                if (data.user_info && data.user_info.name) {
                    const navLinks = document.querySelector('.nav-links');
                    if (navLinks) {
                        const userInfo = document.createElement('span');
                        userInfo.className = 'user-info';
                        userInfo.textContent = `Welcome, ${data.user_info.name}`;
                        navLinks.insertBefore(userInfo, navLinks.firstChild);
                    }
                }
            }
        })
        .catch(error => console.error('Error checking auth status:', error));
}

// Handle form submission
function handleFormSubmit(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Show loading indicator
    const submitButton = form.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.textContent;
    submitButton.textContent = 'Creating presentation...';
    submitButton.disabled = true;
    
    // Submit form data to the API
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to create presentation');
            });
        }
        return response.json();
    })
    .then(data => {
        // Show success message
        showNotification('Success', 'Presentation created successfully!', 'success');
        
        // Reset form
        form.reset();
        
        // Reload presentations list
        loadPresentations();
    })
    .catch(error => {
        showNotification('Error', error.message, 'error');
    })
    .finally(() => {
        // Restore button
        submitButton.textContent = originalButtonText;
        submitButton.disabled = false;
    });
}

// Load user's presentations
function loadPresentations() {
    const presentationsList = document.querySelector('.presentations-list');
    if (!presentationsList) return;
    
    presentationsList.innerHTML = '<p>Loading your presentations...</p>';
    
    fetch('/api/presentations/')
        .then(response => {
            if (!response.ok) {
                if (response.status === 401) {
                    presentationsList.innerHTML = '<p>Please log in to view your presentations.</p>';
                    return null;
                }
                throw new Error('Failed to load presentations');
            }
            return response.json();
        })
        .then(presentations => {
            if (!presentations) return;
            
            if (presentations.length === 0) {
                presentationsList.innerHTML = '<p>You haven\'t created any presentations yet.</p>';
                return;
            }
            
            // Clear loading message and generate presentation cards
            presentationsList.innerHTML = '';
            
            presentations.forEach(presentation => {
                const card = createPresentationCard(presentation);
                presentationsList.appendChild(card);
            });
        })
        .catch(error => {
            console.error('Error loading presentations:', error);
            presentationsList.innerHTML = `<p>Error loading presentations: ${error.message}</p>`;
        });
}

// Create a presentation card element
function createPresentationCard(presentation) {
    const card = document.createElement('div');
    card.className = 'presentation-card';
    
    // Format date
    const createdDate = new Date(presentation.created_at);
    const formattedDate = createdDate.toLocaleDateString();
    
    card.innerHTML = `
        <div class="thumbnail">
            <div class="placeholder">Google Slides</div>
        </div>
        <div class="content">
            <h3>${presentation.title}</h3>
            <p>Created: ${formattedDate}</p>
            <div class="actions">
                <a href="${presentation.google_url}" target="_blank" class="btn primary">Open</a>
                <button data-id="${presentation.id}" class="btn secondary delete-btn">Delete</button>
            </div>
        </div>
    `;
    
    // Add delete event listener
    const deleteBtn = card.querySelector('.delete-btn');
    deleteBtn.addEventListener('click', () => deletePresentation(presentation.id, card));
    
    return card;
}

// Delete a presentation
function deletePresentation(id, cardElement) {
    if (!confirm('Are you sure you want to delete this presentation? This will only remove it from your list; the Google Slides presentation will not be deleted.')) {
        return;
    }
    
    fetch(`/api/presentations/${id}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.error || 'Failed to delete presentation');
            });
        }
        return response.json();
    })
    .then(data => {
        // Remove the card from the DOM
        cardElement.remove();
        showNotification('Success', 'Presentation deleted successfully', 'success');
        
        // If no more presentations, show empty message
        const presentationsList = document.querySelector('.presentations-list');
        if (presentationsList && presentationsList.children.length === 0) {
            presentationsList.innerHTML = '<p>You haven\'t created any presentations yet.</p>';
        }
    })
    .catch(error => {
        showNotification('Error', error.message, 'error');
    });
}

// Show notification
function showNotification(title, message, type = 'info') {
    // Check if notification container exists, create if not
    let notificationContainer = document.querySelector('.notification-container');
    if (!notificationContainer) {
        notificationContainer = document.createElement('div');
        notificationContainer.className = 'notification-container';
        document.body.appendChild(notificationContainer);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <h4>${title}</h4>
        <p>${message}</p>
        <button class="close-btn">&times;</button>
    `;
    
    // Add to container
    notificationContainer.appendChild(notification);
    
    // Add close functionality
    const closeBtn = notification.querySelector('.close-btn');
    closeBtn.addEventListener('click', () => {
        notification.classList.add('fade-out');
        setTimeout(() => {
            notification.remove();
        }, 300);
    });
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('fade-out');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }
    }, 5000);
}