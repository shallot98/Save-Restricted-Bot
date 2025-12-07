/**
 * Lazy Loading Component with Intersection Observer
 * Version: 1.0
 */

(function() {
    'use strict';

    // SVG placeholder image (gray rectangle with loading indicator)
    const PLACEHOLDER_IMAGE = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"%3E%3Crect width="400" height="300" fill="%23f0f0f0"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="16" fill="%23999"%3ELoading...%3C/text%3E%3C/svg%3E';

    function initLazyLoading() {
        // Check if browser supports Intersection Observer
        if (!('IntersectionObserver' in window)) {
            // Fallback: load all images immediately on unsupported browsers
            console.warn('IntersectionObserver not supported, loading all images immediately');
            return;
        }

        // Create Intersection Observer with 200px threshold
        const imageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const img = entry.target;

                    // Swap data-src to src and add loading class
                    if (img.dataset.src) {
                        img.classList.add('image-loading');

                        // Load the actual image
                        const actualImg = new Image();
                        actualImg.onload = function() {
                            img.src = img.dataset.src;
                            img.classList.remove('image-loading');
                            img.classList.add('image-loaded');
                        };
                        actualImg.onerror = function() {
                            img.classList.remove('image-loading');
                            img.classList.add('image-error');
                        };
                        actualImg.src = img.dataset.src;

                        // Stop observing this image
                        observer.unobserve(img);
                    }
                }
            });
        }, {
            rootMargin: '200px', // Load images 200px before entering viewport
            threshold: 0.01
        });

        // Observe all note card images with loading="lazy"
        const lazyImages = document.querySelectorAll('.note-media img[loading="lazy"]');
        lazyImages.forEach(function(img) {
            // Store original src in data-src
            if (img.src && !img.dataset.src) {
                img.dataset.src = img.src;
                img.src = PLACEHOLDER_IMAGE;
            }

            // Start observing
            imageObserver.observe(img);
        });
    }

    // Export to global namespace
    window.LazyLoadManager = {
        init: initLazyLoading,
        PLACEHOLDER_IMAGE: PLACEHOLDER_IMAGE
    };

})();
