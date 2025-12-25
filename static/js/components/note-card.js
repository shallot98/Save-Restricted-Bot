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
        calibrateStatusText: '',
        calibrateElapsedSec: 0,
        _calibrateAbortController: null,
        dnCount: config.dnCount || 0,
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

                const applyLoadedState = (imageEl) => {
                    imageEl.classList.remove('opacity-0', 'image-loading');
                    imageEl.classList.add('image-loaded');
                    const previous = imageEl.previousElementSibling;
                    if (previous && previous.classList && previous.classList.contains('note-media-skeleton')) {
                        previous.remove();
                    }
                };

                const applyErrorState = (imageEl) => {
                    imageEl.classList.remove('opacity-0', 'image-loading');
                    imageEl.classList.add('image-error');
                    const previous = imageEl.previousElementSibling;
                    if (previous && previous.classList && previous.classList.contains('note-media-skeleton')) {
                        previous.remove();
                    }
                };

                imageEls.forEach((imageEl) => {
                    if (imageEl.complete) {
                        if (imageEl.naturalWidth) applyLoadedState(imageEl);
                        else applyErrorState(imageEl);
                        return;
                    }

                    imageEl.addEventListener('load', () => applyLoadedState(imageEl), { once: true });
                    imageEl.addEventListener('error', () => applyErrorState(imageEl), { once: true });
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

        getValidDns() {
            return Array.isArray(this.dns) ? this.dns.filter((d) => d && d.dn) : [];
        },

        getWatchHref(dn) {
            const safeDn = dn === null || dn === undefined ? '' : String(dn);
            return `${this.viewerUrl}${encodeURIComponent(safeDn)}`;
        },

        getCalibrateButtonText() {
            if (this.isCalibrating) {
                const sec = Number.isFinite(this.calibrateElapsedSec) ? this.calibrateElapsedSec : 0;
                return sec > 0 ? `校准中... (${sec}/60s)` : '校准中...';
            }
            const count = this.dnCount || 0;
            return count > 1 ? `校准(${count})` : '校准';
        },

        cancelCalibration() {
            if (!this._calibrateAbortController) return;
            try {
                this._calibrateAbortController.abort();
            } catch (e) {
                // ignore
            }
        },

        // Calibrate note (send magnet links to bot)
        async calibrate() {
            const count = this.dnCount || 0;
            if (count === 0) return;
            const connType = NetworkManager.detectConnectionType();
            const estimatedTime = Math.ceil(count * (['slow-2g', '2g'].includes(connType) ? 15 : 10));
            const calibrateTimeout = NetworkManager.getCalibrationTimeoutMs(count);

            if (!confirm(`校准将向机器人发送 ${count} 个磁力链接，预计需要约 ${estimatedTime} 秒（最长可能 ${Math.ceil(calibrateTimeout / 1000)} 秒）。确定继续？`)) {
                return;
            }

            this.isCalibrating = true;
            this.calibrateStatusText = '校准中...';
            this.calibrateElapsedSec = 0;
            this._calibrateAbortController = new AbortController();

            try {
                const useAsync = window.CalibrationClient && window.CalibrationClient.isAsyncEnabled && window.CalibrationClient.isAsyncEnabled();
                if (!useAsync) {
                    await this._calibrateSync(calibrateTimeout);
                    return;
                }

                let taskId = null;
                try {
                    taskId = await window.CalibrationClient.submitNoteCalibration(this.id);
                } catch (e) {
                    console.warn('异步校准提交失败，回退同步接口:', e);
                    await this._calibrateSync(calibrateTimeout);
                    return;
                }

                this.calibrateStatusText = '校准任务已提交，正在查询状态...';

                const status = await window.CalibrationClient.pollTask(taskId, {
                    signal: this._calibrateAbortController.signal,
                    intervalMs: 1000,
                    maxMs: 60000,
                    onTick: ({ elapsedSec, remainingSec, status }) => {
                        this.calibrateElapsedSec = elapsedSec;
                        const human = status && status.status ? status.status : 'pending';
                        this.calibrateStatusText = `校准中... (${elapsedSec}/60s) 状态: ${human}`;
                        if (remainingSec <= 10) {
                            this.calibrateStatusText = `校准中... (${elapsedSec}/60s) 即将超时，继续等待...`;
                        }
                    }
                });

                const result = status && status.result ? status.result : null;
                if (!result || !result.success) {
                    throw new Error((result && result.error) ? result.error : '校准失败');
                }

                alert(`校准完成!\n总共: ${result.total}\n成功: ${result.success_count}\n失败: ${result.fail_count}`);
                this._applyCalibrationResultToDns(result);
            } catch (error) {
                if (error && error.name === 'AbortError') {
                    alert('已取消校准轮询（任务仍在后台运行）。');
                    return;
                }
                console.error('校准出错:', error);
                alert('校准失败: ' + (error && error.message ? error.message : '未知错误'));
            }
            finally {
                this.isCalibrating = false;
                this.calibrateStatusText = '';
                this.calibrateElapsedSec = 0;
                this._calibrateAbortController = null;
            }
        },

        async _calibrateSync(calibrateTimeout) {
            const response = await NetworkManager.fetchWithRetry(`/api/calibrate/${this.id}`, {
                method: 'POST'
            }, 2, calibrateTimeout);

            const data = await response.json();
            if (!data || !data.success) {
                throw new Error((data && data.error) || '未知错误');
            }

            alert(`校准完成!\n总共: ${data.total}\n成功: ${data.success_count}\n失败: ${data.fail_count}`);
            this._applyCalibrationResultToDns(data);
        },

        _applyCalibrationResultToDns(payload) {
            if (!payload || !Array.isArray(payload.results)) return;
            const updates = new Map();
            payload.results.forEach((r) => {
                if (!r || !r.success) return;
                if (!r.info_hash || !r.filename) return;
                updates.set(String(r.info_hash), String(r.filename));
            });

            if (updates.size > 0 && Array.isArray(this.dns)) {
                this.dns = this.dns.map((d) => {
                    if (!d || !d.info_hash) return d;
                    const key = String(d.info_hash);
                    if (!updates.has(key)) return d;
                    return { ...d, dn: updates.get(key) };
                });
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

            const validDns = this.getValidDns();
            optionsList.innerHTML = '';

            validDns.forEach((item) => {
                const dn = String(item.dn);
                const option = document.createElement('a');
                option.href = this.getWatchHref(dn);
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
