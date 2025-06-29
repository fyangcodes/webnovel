/**
 * Translation utilities for the webnovel application
 */

class TranslationManager {
    constructor() {
        this.csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
            document.querySelector('meta[name=csrf-token]')?.content;
    }

    /**
     * Initiate a translation for a chapter
     * @param {number} chapterId - The ID of the original chapter
     * @param {number} languageId - The ID of the target language
     * @param {Function} onSuccess - Callback function on success
     * @param {Function} onError - Callback function on error
     */
    initiateTranslation(chapterId, languageId, onSuccess = null, onError = null) {
        const url = `/books/chapters/${chapterId}/initiate-translation/${languageId}/`;

        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Translation initiated:', data.message);
                    if (onSuccess) onSuccess(data);
                    this.showNotification(data.message, 'success');
                } else {
                    console.error('Translation failed:', data.error);
                    if (onError) onError(data.error);
                    this.showNotification(data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Network error:', error);
                const errorMsg = 'Network error occurred while initiating translation.';
                if (onError) onError(errorMsg);
                this.showNotification(errorMsg, 'error');
            });
    }

    /**
     * Check translation status for a chapter
     * @param {number} chapterId - The ID of the chapter
     * @param {Function} onSuccess - Callback function on success
     * @param {Function} onError - Callback function on error
     */
    checkTranslationStatus(chapterId, onSuccess = null, onError = null) {
        const url = `/books/chapters/${chapterId}/check-translation-status/`;

        fetch(url, {
            method: 'GET',
            headers: {
                'X-CSRFToken': this.csrfToken
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (onSuccess) onSuccess(data);
                } else {
                    if (onError) onError(data.error);
                    this.showNotification(data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Network error:', error);
                const errorMsg = 'Network error occurred while checking translation status.';
                if (onError) onError(errorMsg);
                this.showNotification(errorMsg, 'error');
            });
    }

    /**
     * Poll translation status until completion
     * @param {number} chapterId - The ID of the chapter
     * @param {number} interval - Polling interval in milliseconds (default: 5000)
     * @param {Function} onComplete - Callback when translation is complete
     * @param {Function} onError - Callback on error
     */
    pollTranslationStatus(chapterId, interval = 5000, onComplete = null, onError = null) {
        const poll = () => {
            this.checkTranslationStatus(chapterId, (data) => {
                const hasTranslating = data.translations.some(t => t.is_translating);
                const hasError = data.translations.some(t => t.has_error);

                if (hasError) {
                    if (onError) onError('Translation failed with errors');
                    return;
                }

                if (hasTranslating) {
                    // Continue polling
                    setTimeout(poll, interval);
                } else {
                    // Translation complete
                    if (onComplete) onComplete(data);
                    this.showNotification('Translation completed!', 'success');
                }
            }, (error) => {
                if (onError) onError(error);
            });
        };

        // Start polling
        poll();
    }

    /**
     * Show a notification message
     * @param {string} message - The message to display
     * @param {string} type - The type of notification ('success', 'error', 'info')
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
        notification.style.position = 'fixed';
        notification.style.top = '20px';
        notification.style.right = '20px';
        notification.style.zIndex = '9999';
        notification.style.minWidth = '300px';

        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

}

// Initialize translation manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    window.translationManager = new TranslationManager();
}); 