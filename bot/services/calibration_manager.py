"""
自动校准任务管理器
负责处理磁力链接的自动校准任务
"""
import logging
import os
import re
import subprocess
import sys
from typing import Optional, List, Dict
from urllib.parse import quote
from database import (
    get_calibration_config,
    add_calibration_task,
    get_pending_calibration_tasks,
    update_calibration_task,
    get_note_by_id,
    update_note_with_calibrated_dn,
    update_note_with_calibrated_dns,  # 多磁力链接更新
    get_calibration_stats
)

logger = logging.getLogger(__name__)


class CalibrationManager:
    """校准任务管理器"""

    def __init__(self):
        self.config = None
        self.reload_config()

    def reload_config(self):
        """重新加载配置"""
        self.config = get_calibration_config()
        if self.config:
            logger.info(f"📋 校准配置已加载: enabled={self.config['enabled']}, filter_mode={self.config['filter_mode']}")
        else:
            logger.warning("⚠️ 无法加载校准配置")

    def is_enabled(self) -> bool:
        """检查自动校准是否启用"""
        if not self.config:
            self.reload_config()
        return self.config and self.config.get('enabled', 0) == 1

    def should_calibrate_note(self, note: Dict) -> bool:
        """判断笔记是否需要校准

        Args:
            note: 笔记字典

        Returns:
            是否需要校准
        """
        if not self.is_enabled():
            return False

        magnet_link = note.get('magnet_link')
        message_text = note.get('message_text', '')

        # 如果既没有magnet_link也没有文本中的磁力链接，不需要校准
        all_magnets = self.extract_all_magnets_from_text(message_text)
        if not magnet_link and not all_magnets:
            return False

        filter_mode = self.config.get('filter_mode', 'empty_only')

        # 检查filename字段是否为空（真正校准成功后才会填充）
        filename = note.get('filename')

        if filter_mode == 'empty_only':
            # 仅校准未校准过的笔记
            # 判断标准：filename为空（未真正校准过）
            # 注意：magnet_link的dn参数可能是网页添加时自动提取的，不算真正校准
            if not filename or filename.strip() == '':
                return True
            else:
                # filename不为空，说明已经校准过
                return False
        elif filter_mode == 'all':
            # 校准所有笔记
            return True

        return False

    def extract_magnet_hash(self, magnet_link: str) -> Optional[str]:
        """从磁力链接提取info hash

        Args:
            magnet_link: 磁力链接

        Returns:
            info hash（大写）
        """
        match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet_link, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def extract_all_magnets_from_text(self, message_text: str) -> List[str]:
        """从笔记文本中提取所有磁力链接

        Args:
            message_text: 笔记文本

        Returns:
            磁力链接列表
        """
        if not message_text:
            return []

        # 正则匹配所有magnet链接
        magnet_pattern = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]+(?:[&?][^\s\n]*)?'
        magnets = re.findall(magnet_pattern, message_text, re.IGNORECASE)

        return magnets

    def extract_all_dns_from_note(self, note: Dict) -> List[Dict]:
        """从笔记中提取所有磁力链接的信息（与app.py保持一致）

        Args:
            note: 笔记字典

        Returns:
            [{'magnet': 磁力链接, 'info_hash': info_hash}, ...]
        """
        dns = []
        message_text = note.get('message_text', '')

        # 从笔记文本提取所有磁力链接
        all_magnets = self.extract_all_magnets_from_text(message_text)

        # 如果没有找到任何磁力链接，尝试使用magnet_link字段
        if not all_magnets and note.get('magnet_link'):
            all_magnets = [note['magnet_link']]

        # 为每个磁力链接提取info_hash
        for magnet in all_magnets:
            # 提取info_hash
            info_hash_match = re.search(r'xt=urn:btih:([a-zA-Z0-9]+)', magnet, re.IGNORECASE)
            info_hash = info_hash_match.group(1).upper() if info_hash_match else None

            if info_hash:
                dns.append({
                    'magnet': magnet,
                    'info_hash': info_hash
                })

        return dns

    def add_note_to_calibration_queue(self, note_id: int) -> bool:
        """将笔记添加到校准队列

        Args:
            note_id: 笔记ID

        Returns:
            是否成功添加
        """
        try:
            logger.info(f"🔄 开始处理校准任务: note_id={note_id}")

            note = get_note_by_id(note_id)
            if not note:
                logger.warning(f"⚠️ 笔记 {note_id} 不存在")
                return False

            logger.info(f"✅ 笔记已找到: note_id={note_id}, magnet_link={'有' if note.get('magnet_link') else '无'}")

            if not self.should_calibrate_note(note):
                logger.info(f"⏭️ 笔记 {note_id} 不需要校准（filter_mode={self.config.get('filter_mode')}）")
                return False

            logger.info(f"✅ 笔记需要校准: note_id={note_id}")

            magnet_hash = self.extract_magnet_hash(note['magnet_link'])
            if not magnet_hash:
                logger.warning(f"⚠️ 无法从笔记 {note_id} 提取磁力hash")
                return False

            logger.info(f"✅ 磁力hash已提取: note_id={note_id}, hash={magnet_hash[:16]}...")

            first_delay = self.config.get('first_delay', 600)
            task_id = add_calibration_task(note_id, magnet_hash, first_delay)

            if task_id:
                logger.info(f"🎉 校准任务已添加: task_id={task_id}, note_id={note_id}, delay={first_delay}秒")
            else:
                logger.error(f"❌ 添加校准任务失败: note_id={note_id}")

            return task_id is not None

        except Exception as e:
            logger.error(f"❌ 添加校准任务异常: note_id={note_id}, error={e}", exc_info=True)
            return False

    def calibrate_magnet(self, magnet_hash: str, timeout: int = 30) -> Optional[str]:
        """校准单个磁力链接，获取真实文件名

        Args:
            magnet_hash: 磁力链接的info hash
            timeout: 超时时间（秒）

        Returns:
            文件名，失败返回None
        """
        try:
            # 调用独立的校准脚本
            # 容器内工作目录是/app,宿主机是/root/Save-Restricted-Bot
            script_path = '/app/calibrate_helper.py' if os.path.exists('/app/calibrate_helper.py') else os.path.join(os.path.dirname(__file__), '../../calibrate_helper.py')

            result = subprocess.run(
                [sys.executable, script_path, magnet_hash],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0 and result.stdout.strip():
                filename = result.stdout.strip()
                logger.info(f"✅ 成功获取文件名: {filename[:50]}...")
                return filename
            else:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                logger.warning(f"⚠️ 校准失败: {error_msg[:100]}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️ 校准超时（{timeout}秒）")
            return None
        except Exception as e:
            logger.error(f"校准过程出错: {e}", exc_info=True)
            return None

    def process_calibration_task(self, task: Dict) -> bool:
        """处理单个校准任务（支持多磁力链接）

        Args:
            task: 任务字典

        Returns:
            是否成功
        """
        task_id = task['id']
        note_id = task['note_id']
        retry_count = task['retry_count']

        logger.info(f"🔧 开始处理校准任务: task_id={task_id}, note_id={note_id}, retry={retry_count}")

        try:
            # 获取笔记信息
            note = get_note_by_id(note_id)
            if not note:
                logger.warning(f"笔记 {note_id} 不存在，删除任务")
                update_calibration_task(task_id, 'failed', '笔记不存在')
                return False

            # 检查笔记是否已经被校准过（防止重复校准）
            if not self.should_calibrate_note(note):
                logger.info(f"✅ 笔记 {note_id} 已经校准过，直接标记任务成功")
                update_calibration_task(task_id, 'success')
                return True

            # 提取所有磁力链接（与Web API保持一致）
            all_dns = self.extract_all_dns_from_note(note)

            if not all_dns:
                logger.warning(f"⚠️ 笔记 {note_id} 没有找到磁力链接")
                update_calibration_task(task_id, 'failed', '没有找到磁力链接')
                return False

            logger.info(f"📋 发现 {len(all_dns)} 个磁力链接，开始批量校准")

            # 批量校准所有磁力链接
            timeout = self.config.get('timeout_per_magnet', 30)
            calibrated_results = []

            for idx, dn_info in enumerate(all_dns, 1):
                info_hash = dn_info['info_hash']
                old_magnet = dn_info['magnet']

                logger.info(f"🔄 校准第 {idx}/{len(all_dns)} 个磁力链接: {info_hash[:16]}...")

                # 调用校准脚本
                filename = self.calibrate_magnet(info_hash, timeout)

                if filename:
                    logger.info(f"✅ 第 {idx} 个磁力链接校准成功: {filename[:50]}...")
                    calibrated_results.append({
                        'info_hash': info_hash,
                        'old_magnet': old_magnet,
                        'filename': filename,
                        'success': True
                    })
                else:
                    logger.warning(f"⚠️ 第 {idx} 个磁力链接校准失败")
                    calibrated_results.append({
                        'info_hash': info_hash,
                        'old_magnet': old_magnet,
                        'error': '校准失败',
                        'success': False
                    })

            # 统计成功和失败
            success_count = sum(1 for r in calibrated_results if r['success'])
            fail_count = len(calibrated_results) - success_count

            logger.info(f"📊 校准完成: 成功 {success_count}/{len(calibrated_results)}, 失败 {fail_count}")

            # 如果至少有一个成功，就更新数据库
            if success_count > 0:
                # 批量更新数据库（与Web API保持一致）
                update_success = update_note_with_calibrated_dns(note_id, calibrated_results)

                if update_success:
                    logger.info(f"✅ 笔记 {note_id} 更新成功（{success_count}个磁力链接已校准）")
                    update_calibration_task(task_id, 'success')
                    return True
                else:
                    logger.error(f"❌ 更新笔记 {note_id} 失败")
                    update_calibration_task(task_id, 'failed', '更新笔记失败')
                    return False
            else:
                # 所有磁力链接都校准失败，判断是否需要重试
                max_retries = self.config.get('max_retries', 3)

                if retry_count < max_retries:
                    # 计算下次重试延迟（渐进式退避）
                    retry_delays = [
                        self.config.get('retry_delay_1', 3600),   # 1小时
                        self.config.get('retry_delay_2', 14400),  # 4小时
                        self.config.get('retry_delay_3', 28800),  # 8小时
                    ]
                    next_delay = retry_delays[min(retry_count, len(retry_delays) - 1)]

                    logger.info(f"⏰ 所有磁力链接校准失败，将在 {next_delay // 3600} 小时后重试")
                    update_calibration_task(task_id, 'retrying', '校准失败，等待重试', next_delay)
                    return False
                else:
                    # 超过最大重试次数，标记失败并在笔记前添加标记
                    logger.warning(f"❌ 校准失败（已重试{max_retries}次）: note_id={note_id}")

                    # 在message_text前添加 #* 标记
                    if note.get('message_text'):
                        from database import update_note
                        marked_text = f"#* {note['message_text']}"
                        update_note(note_id, marked_text)

                    update_calibration_task(task_id, 'failed', f'校准失败（已重试{max_retries}次）')
                    return False

        except Exception as e:
            logger.error(f"处理校准任务时出错: {e}", exc_info=True)
            update_calibration_task(task_id, 'failed', str(e))
            return False

    def process_pending_tasks(self, max_concurrent: int = 5):
        """批量处理待执行的校准任务

        Args:
            max_concurrent: 最大并发数
        """
        if not self.is_enabled():
            logger.debug("自动校准未启用")
            return

        try:
            tasks = get_pending_calibration_tasks(limit=max_concurrent)

            if not tasks:
                logger.debug("没有待处理的校准任务")
                return

            logger.info(f"📋 发现 {len(tasks)} 个待处理的校准任务")

            success_count = 0
            for task in tasks:
                try:
                    if self.process_calibration_task(task):
                        success_count += 1
                except Exception as e:
                    logger.error(f"处理任务 {task['id']} 时出错: {e}", exc_info=True)

            logger.info(f"✅ 批量处理完成: 成功 {success_count}/{len(tasks)}")

        except Exception as e:
            logger.error(f"批量处理校准任务失败: {e}", exc_info=True)

    def get_stats(self) -> Dict:
        """获取校准任务统计信息"""
        return get_calibration_stats()


# 全局实例
_calibration_manager = None


def get_calibration_manager() -> CalibrationManager:
    """获取全局校准管理器实例"""
    global _calibration_manager
    if _calibration_manager is None:
        _calibration_manager = CalibrationManager()
    return _calibration_manager
