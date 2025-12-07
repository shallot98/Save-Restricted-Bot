/**
 * Modal Component (Image Preview)
 * Version: 1.0
 */

(function() {
    'use strict';

    const ModalManager = {
        // Open image modal
        openImageModal: function(src) {
            const modal = document.getElementById('imageModal');
            const img = document.getElementById('modalImage');
            modal.classList.add('active');
            img.src = src;
            document.body.style.overflow = 'hidden';
        },

        // Close image modal
        closeImageModal: function() {
            document.getElementById('imageModal').classList.remove('active');
            document.body.style.overflow = 'auto';
        },

        // Initialize modal event listeners
        init: function() {
            // ESC key to close modal
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    ModalManager.closeImageModal();
                }
            });
        }
    };

    // Export to global namespace
    window.ModalManager = ModalManager;

})();
