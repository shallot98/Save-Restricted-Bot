/**
 * Note Card Alpine.js Component
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('noteCard', (config) => ({
        id: config.id,
        isFavorite: config.isFavorite,
        isTogglingFavorite: false,
        isExpanded: false,
        isCalibrating: false,
        mediaPaths: config.mediaPaths || [],
        viewerUrl: config.viewerUrl || '',
        dns: config.dns || [],
        
        // Initialization
        init() {
            this.$nextTick(() => {
                const textEl = document.getElementById(`text-${this.id}`);
                const btn = document.getElementById(`expand-btn-${this.id}`);
                if (!textEl || !btn) return;

                const isClamped = textEl.classList.contains('line-clamp-3');
                if (!isClamped) {
                    btn.classList.remove('hidden');
                    return;
                }

                const collapsedHeight = textEl.clientHeight;
                textEl.classList.remove('line-clamp-3');
                const expandedHeight = textEl.clientHeight;
                textEl.classList.add('line-clamp-3');

                if (expandedHeight > collapsedHeight + 1) {
                    btn.classList.remove('hidden');
                }
            });

            this.$nextTick(() => {
                const imageEls = this.$el.querySelectorAll('[data-note-media-img]');
                if (!imageEls || imageEls.length === 0) return;

                imageEls.forEach((imageEl) => {
                    if (!imageEl.complete) return;
                    if (!imageEl.naturalWidth) return;

                    imageEl.classList.remove('opacity-0', 'image-loading');
                    imageEl.classList.add('image-loaded');
                    const previous = imageEl.previousElementSibling;
                    if (previous && previous.classList && previous.classList.contains('note-media-skeleton')) {
                        previous.remove();
                    }
                });
            });
        },

        playFavoriteAnimation() {
            const btn = this.$refs && this.$refs.favoriteBtn;
            if (!btn) return;

            btn.classList.remove('favorite-animation');
            void btn.offsetWidth;
            btn.classList.add('favorite-animation');

            const cleanup = () => btn.classList.remove('favorite-animation');
            btn.addEventListener('animationend', cleanup, { once: true });
            setTimeout(cleanup, 500);
        },

        // Toggle favorite status
        async toggleFavorite() {
            if (this.isTogglingFavorite) return;

            this.isTogglingFavorite = true;
            const previousState = this.isFavorite;
            this.isFavorite = !this.isFavorite;
            this.playFavoriteAnimation();

            try {
                const response = await NetworkManager.fetchWithRetry(`/toggle_favorite/${this.id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();

                if (!response.ok || !data || !data.success) {
                    throw new Error((data && data.error) || `HTTP ${response.status}: ${response.statusText}`);
                }

                if (typeof data.is_favorite === 'boolean') {
                    this.isFavorite = data.is_favorite;
                }
            } catch (error) {
                console.error('收藏操作失败:', error);
                this.isFavorite = previousState;
                alert(error && error.message ? `收藏操作失败: ${error.message}` : '收藏操作失败，请稍后再试');
            } finally {
                this.isTogglingFavorite = false;
            }
        },

        // Toggle text expansion
        toggleText() {
            this.isExpanded = !this.isExpanded;
            const textEl = document.getElementById(`text-${this.id}`);
            if (this.isExpanded) {
                textEl.classList.remove('line-clamp-3');
            } else {
                textEl.classList.add('line-clamp-3');
            }
        },

        // Calibrate note (send magnet links to bot)
        async calibrate() {
            const count = config.dnCount || 0;
            const connType = NetworkManager.detectConnectionType();
            const estimatedTime = Math.ceil(count * (['slow-2g', '2g'].includes(connType) ? 15 : 10));

            if (!confirm(`校准将向机器人发送 ${count} 个磁力链接，预计需要约 ${estimatedTime} 秒。确定继续？`)) {
                return;
            }

            this.isCalibrating = true;
            try {
                // 计算自定义超时时间
                const baseTimeout = NetworkManager.getApiTimeout();
                const calibrateTimeout = Math.min(baseTimeout * count, 60000); // 最多60秒

                const response = await NetworkManager.fetchWithRetry(`/api/calibrate/${this.id}`, {
                    method: 'POST'
                }, 2, calibrateTimeout); // 使用自定义超时
                const data = await response.json();
                
                if (data.success) {
                    alert(`校准完成!\n总共: ${data.total}\n成功: ${data.success_count}\n失败: ${data.fail_count}`);
                    location.reload();
                } else {
                    throw new Error(data.error || '未知错误');
                }
            } catch (error) {
                console.error('校准出错:', error);
                alert('校准失败: ' + error.message);
                this.isCalibrating = false;
            }
        },

        // Edit note
        edit() {
            if (typeof window.editNote === 'function') {
                window.editNote(this.id);
                return;
            }

            const textEl = document.getElementById(`text-${this.id}`);
            const currentText = textEl ? textEl.innerText : '';
            this.$dispatch('open-edit-modal', {
                noteId: this.id,
                text: currentText
            });
        },

        // Show watch options
        showWatchOptions() {
            const modal = document.getElementById('watchModal');
            const optionsList = document.getElementById('watchOptionsList');
            if (!modal || !optionsList) return;

            const validDns = Array.isArray(this.dns) ? this.dns.filter((d) => d && d.dn) : [];
            optionsList.innerHTML = '';

            validDns.forEach((item) => {
                const dn = String(item.dn);
                const option = document.createElement('a');
                option.href = `${this.viewerUrl}${dn}`;
                option.target = '_blank';
                option.className = 'block p-3 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition';
                option.textContent = dn;
                optionsList.appendChild(option);
            });

            modal.classList.remove('hidden');
            modal.classList.add('flex');
        },

        // Delete note
        async deleteNote() {
            if (!confirm('确定要删除这条笔记吗? 此操作不可撤销。')) return;

            try {
                const response = await NetworkManager.fetchWithRetry(`/delete_note/${this.id}`, {
                    method: 'POST'
                });
                const data = await response.json();
                if (data.success) {
                    // Smoothly remove the card from UI
                    this.$el.classList.add('opacity-0', 'scale-95');
                    setTimeout(() => {
                        this.$el.remove();
                        // If it was the last note on page, maybe reload or show empty state
                    }, 300);
                } else {
                    alert('删除失败: ' + (data.error || '未知错误'));
                }
            } catch (error) {
                console.error('删除笔记失败:', error);
                alert('网络错误，请稍后再试');
            }
        },

        // Open image gallery
        openGallery(startIndex = 0) {
            const mediaPaths = this.mediaPaths.length > 0
                ? this.mediaPaths
                : (config.mediaPath ? [config.mediaPath] : []);

            if (mediaPaths.length === 0) return;

            if (typeof window.openImageGallery === 'function') {
                window.openImageGallery(this.id, mediaPaths, startIndex);
                return;
            }

            this.$dispatch('open-gallery', {
                noteId: this.id,
                mediaPaths,
                startIndex
            });
        }
    }));
});
