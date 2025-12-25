"""
媒体文件清理模块
定期清理旧的或未使用的媒体文件
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
import sqlite3
from config import MEDIA_DIR
from database import DATABASE_FILE

logger = logging.getLogger(__name__)


class MediaCleaner:
    """媒体文件清理器"""
    
    def __init__(self, media_dir: str = MEDIA_DIR, db_file: str = DATABASE_FILE):
        """
        初始化清理器
        
        Args:
            media_dir: 媒体文件目录
            db_file: 数据库文件路径
        """
        self.media_dir = media_dir
        self.db_file = db_file
    
    def get_all_media_files(self) -> List[str]:
        """
        获取所有媒体文件列表
        
        Returns:
            List[str]: 文件路径列表
        """
        media_files = []
        
        if not os.path.exists(self.media_dir):
            logger.warning(f"媒体目录不存在: {self.media_dir}")
            return media_files
        
        for root, dirs, files in os.walk(self.media_dir):
            for file in files:
                file_path = os.path.join(root, file)
                media_files.append(file_path)
        
        return media_files
    
    def get_referenced_media_files(self) -> set:
        """
        获取数据库中引用的媒体文件
        
        Returns:
            set: 被引用的文件路径集合
        """
        referenced_files = set()
        
        try:
            conn = sqlite3.connect(self.db_file)
            try:
                from src.infrastructure.monitoring.performance.db_tracer import get_db_tracer

                conn = get_db_tracer().enable(conn)
            except Exception as e:
                logger.debug("db_tracer 启用失败，已忽略: %s", e, exc_info=True)
            cursor = conn.cursor()
            
            # 查询 media_path
            cursor.execute("SELECT media_path FROM notes WHERE media_path IS NOT NULL")
            for row in cursor.fetchall():
                if row[0]:
                    referenced_files.add(row[0])
            
            # 查询 media_paths (JSON 数组)
            cursor.execute("SELECT media_paths FROM notes WHERE media_paths IS NOT NULL")
            for row in cursor.fetchall():
                if row[0]:
                    import json
                    try:
                        paths = json.loads(row[0])
                        referenced_files.update(paths)
                    except json.JSONDecodeError:
                        pass
            
            conn.close()
            
        except Exception as e:
            logger.error(f"查询数据库失败: {e}")
        
        return referenced_files
    
    def find_orphaned_files(self) -> List[str]:
        """
        查找孤立文件（未被数据库引用）
        
        Returns:
            List[str]: 孤立文件路径列表
        """
        all_files = self.get_all_media_files()
        referenced_files = self.get_referenced_media_files()
        
        orphaned_files = []
        for file_path in all_files:
            # 检查文件是否被引用
            is_referenced = False
            for ref_path in referenced_files:
                if ref_path in file_path or file_path.endswith(os.path.basename(ref_path)):
                    is_referenced = True
                    break
            
            if not is_referenced:
                orphaned_files.append(file_path)
        
        return orphaned_files
    
    def find_old_files(self, days: int = 90) -> List[Tuple[str, float]]:
        """
        查找超过指定天数的旧文件
        
        Args:
            days: 天数阈值
            
        Returns:
            List[Tuple[str, float]]: (文件路径, 文件大小) 列表
        """
        threshold_time = time.time() - (days * 24 * 60 * 60)
        old_files = []
        
        all_files = self.get_all_media_files()
        for file_path in all_files:
            try:
                file_stat = os.stat(file_path)
                if file_stat.st_mtime < threshold_time:
                    old_files.append((file_path, file_stat.st_size))
            except OSError:
                pass
        
        return old_files
    
    def cleanup_orphaned_files(self, dry_run: bool = True) -> Tuple[int, int]:
        """
        清理孤立文件
        
        Args:
            dry_run: 是否为模拟运行（不实际删除）
            
        Returns:
            Tuple[int, int]: (删除文件数, 释放空间字节数)
        """
        orphaned_files = self.find_orphaned_files()
        
        if not orphaned_files:
            logger.info("✅ 没有发现孤立文件")
            return 0, 0
        
        deleted_count = 0
        freed_space = 0
        
        logger.info(f"发现 {len(orphaned_files)} 个孤立文件")
        
        for file_path in orphaned_files:
            try:
                file_size = os.path.getsize(file_path)
                
                if dry_run:
                    logger.info(f"[模拟] 删除: {file_path} ({file_size} 字节)")
                else:
                    os.remove(file_path)
                    logger.info(f"删除: {file_path} ({file_size} 字节)")
                
                deleted_count += 1
                freed_space += file_size
                
            except Exception as e:
                logger.error(f"删除文件失败 {file_path}: {e}")
        
        return deleted_count, freed_space
    
    def cleanup_old_files(self, days: int = 90, dry_run: bool = True) -> Tuple[int, int]:
        """
        清理旧文件
        
        Args:
            days: 天数阈值
            dry_run: 是否为模拟运行
            
        Returns:
            Tuple[int, int]: (删除文件数, 释放空间字节数)
        """
        old_files = self.find_old_files(days)
        
        if not old_files:
            logger.info(f"✅ 没有发现超过 {days} 天的旧文件")
            return 0, 0
        
        deleted_count = 0
        freed_space = 0
        
        logger.info(f"发现 {len(old_files)} 个超过 {days} 天的旧文件")
        
        for file_path, file_size in old_files:
            try:
                if dry_run:
                    logger.info(f"[模拟] 删除: {file_path} ({file_size} 字节)")
                else:
                    os.remove(file_path)
                    logger.info(f"删除: {file_path} ({file_size} 字节)")
                
                deleted_count += 1
                freed_space += file_size
                
            except Exception as e:
                logger.error(f"删除文件失败 {file_path}: {e}")
        
        return deleted_count, freed_space
    
    def get_storage_stats(self) -> dict:
        """
        获取存储统计信息
        
        Returns:
            dict: 统计信息字典
        """
        all_files = self.get_all_media_files()
        total_size = sum(os.path.getsize(f) for f in all_files if os.path.exists(f))
        
        orphaned_files = self.find_orphaned_files()
        orphaned_size = sum(os.path.getsize(f) for f in orphaned_files if os.path.exists(f))
        
        return {
            'total_files': len(all_files),
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'orphaned_files': len(orphaned_files),
            'orphaned_size': orphaned_size,
            'orphaned_size_mb': orphaned_size / (1024 * 1024),
        }
    
    def print_stats(self):
        """打印存储统计信息"""
        stats = self.get_storage_stats()
        
        logger.info("=" * 60)
        logger.info("📊 媒体存储统计")
        logger.info("=" * 60)
        logger.info(f"总文件数: {stats['total_files']}")
        logger.info(f"总大小: {stats['total_size_mb']:.2f} MB")
        logger.info(f"孤立文件数: {stats['orphaned_files']}")
        logger.info(f"孤立文件大小: {stats['orphaned_size_mb']:.2f} MB")
        logger.info("=" * 60)


# 命令行工具
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="媒体文件清理工具")
    parser.add_argument("--stats", action="store_true", help="显示存储统计")
    parser.add_argument("--cleanup-orphaned", action="store_true", help="清理孤立文件")
    parser.add_argument("--cleanup-old", type=int, metavar="DAYS", help="清理超过指定天数的文件")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行（不实际删除）")
    
    args = parser.parse_args()
    
    cleaner = MediaCleaner()
    
    if args.stats:
        cleaner.print_stats()
    
    if args.cleanup_orphaned:
        deleted, freed = cleaner.cleanup_orphaned_files(dry_run=args.dry_run)
        logger.info(f"{'[模拟] ' if args.dry_run else ''}删除 {deleted} 个文件，释放 {freed / (1024*1024):.2f} MB")
    
    if args.cleanup_old:
        deleted, freed = cleaner.cleanup_old_files(days=args.cleanup_old, dry_run=args.dry_run)
        logger.info(f"{'[模拟] ' if args.dry_run else ''}删除 {deleted} 个文件，释放 {freed / (1024*1024):.2f} MB")
