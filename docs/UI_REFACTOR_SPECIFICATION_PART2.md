# Save-Restricted-Bot UI重构方案 - 第二部分（续）

> 接续 UI_REFACTOR_SPECIFICATION.md

---

## 2.4 搜索和高级筛选（续）

### 2.4.2 AdvancedSearch组件

**AdvancedSearch.vue - 高级搜索对话框**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTagsStore } from '@/stores/tags'
import { useNotesStore } from '@/stores/notes'

interface SearchFilters {
  query?: string
  sources?: string[]
  tags?: number[]
  dateFrom?: string
  dateTo?: string
  mediaType?: string[]
  favorite?: boolean
  hasMedia?: boolean
  hasLink?: boolean
}

interface Props {
  modelValue: boolean
  initialFilters?: SearchFilters
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'apply', filters: SearchFilters): void
  (e: 'reset'): void
}>()

const tagsStore = useTagsStore()
const notesStore = useNotesStore()

// 筛选条件
const filters = ref<SearchFilters>({
  query: props.initialFilters?.query || '',
  sources: props.initialFilters?.sources || [],
  tags: props.initialFilters?.tags || [],
  dateFrom: props.initialFilters?.dateFrom || '',
  dateTo: props.initialFilters?.dateTo || '',
  mediaType: props.initialFilters?.mediaType || [],
  favorite: props.initialFilters?.favorite || false,
  hasMedia: props.initialFilters?.hasMedia || false,
  hasLink: props.initialFilters?.hasLink || false,
})

// 选项数据
const sources = computed(() => notesStore.sources)
const tags = computed(() => tagsStore.tags)
const mediaTypes = [
  { label: '图片', value: 'photo' },
  { label: '视频', value: 'video' },
  { label: 'GIF动图', value: 'animation' },
  { label: '文档', value: 'document' },
]

// 应用筛选
const applyFilters = () => {
  emit('apply', { ...filters.value })
  emit('update:modelValue', false)
}

// 重置筛选
const resetFilters = () => {
  filters.value = {
    query: '',
    sources: [],
    tags: [],
    dateFrom: '',
    dateTo: '',
    mediaType: [],
    favorite: false,
    hasMedia: false,
    hasLink: false,
  }
  emit('reset')
}

// 关闭对话框
const close = () => {
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="高级搜索"
    width="700px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form :model="filters" label-width="100px" label-position="left">
      <!-- 关键词搜索 -->
      <el-form-item label="关键词">
        <el-input
          v-model="filters.query"
          placeholder="输入搜索关键词..."
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </el-form-item>

      <!-- 来源筛选 -->
      <el-form-item label="来源">
        <el-select
          v-model="filters.sources"
          multiple
          collapse-tags
          placeholder="选择来源频道"
          style="width: 100%"
        >
          <el-option
            v-for="source in sources"
            :key="source.id"
            :label="source.name"
            :value="source.id"
          />
        </el-select>
      </el-form-item>

      <!-- 标签筛选 -->
      <el-form-item label="标签">
        <el-select
          v-model="filters.tags"
          multiple
          collapse-tags
          placeholder="选择标签"
          style="width: 100%"
        >
          <el-option
            v-for="tag in tags"
            :key="tag.id"
            :label="tag.name"
            :value="tag.id"
          >
            <span
              class="tag-color-dot"
              :style="{ backgroundColor: tag.color }"
            />
            {{ tag.name }}
          </el-option>
        </el-select>
      </el-form-item>

      <!-- 日期范围 -->
      <el-form-item label="日期范围">
        <el-date-picker
          v-model="filters.dateFrom"
          type="date"
          placeholder="开始日期"
          style="width: 48%; margin-right: 4%"
        />
        <el-date-picker
          v-model="filters.dateTo"
          type="date"
          placeholder="结束日期"
          style="width: 48%"
        />
      </el-form-item>

      <!-- 媒体类型 -->
      <el-form-item label="媒体类型">
        <el-checkbox-group v-model="filters.mediaType">
          <el-checkbox
            v-for="type in mediaTypes"
            :key="type.value"
            :label="type.value"
          >
            {{ type.label }}
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>

      <!-- 其他筛选 -->
      <el-form-item label="其他条件">
        <el-checkbox v-model="filters.favorite">
          仅显示收藏
        </el-checkbox>
        <el-checkbox v-model="filters.hasMedia">
          包含媒体文件
        </el-checkbox>
        <el-checkbox v-model="filters.hasLink">
          包含链接
        </el-checkbox>
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="resetFilters">重置</el-button>
        <el-button @click="close">取消</el-button>
        <el-button type="primary" @click="applyFilters">
          应用筛选
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped lang="scss">
.tag-color-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
```

---

## 2.5 标签和分类系统

### 2.5.1 TagSelector组件

**TagSelector.vue - 标签选择器**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTagsStore } from '@/stores/tags'
import type { Tag } from '@/types/tag'

interface Props {
  modelValue: number[]
  max?: number
}

const props = withDefaults(defineProps<Props>(), {
  max: 10
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number[]): void
}>()

const tagsStore = useTagsStore()

const selectedTags = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const availableTags = computed(() => tagsStore.tags)
const inputVisible = ref(false)
const newTagName = ref('')

// 添加标签
const handleAddTag = async () => {
  if (!newTagName.value.trim()) return
  
  const tag = await tagsStore.createTag({
    name: newTagName.value.trim(),
    color: getRandomColor()
  })
  
  if (tag) {
    selectedTags.value = [...selectedTags.value, tag.id]
  }
  
  inputVisible.value = false
  newTagName.value = ''
}

// 移除标签
const handleRemoveTag = (tagId: number) => {
  selectedTags.value = selectedTags.value.filter(id => id !== tagId)
}

// 获取标签信息
const getTag = (tagId: number): Tag | undefined => {
  return availableTags.value.find(t => t.id === tagId)
}

// 随机颜色
const getRandomColor = () => {
  const colors = [
    '#667eea', '#764ba2', '#f093fb', '#4facfe',
    '#43e97b', '#fa709a', '#fee140', '#30cfd0'
  ]
  return colors[Math.floor(Math.random() * colors.length)]
}
</script>

<template>
  <div class="tag-selector">
    <!-- 已选标签 -->
    <div class="selected-tags">
      <el-tag
        v-for="tagId in selectedTags"
        :key="tagId"
        :color="getTag(tagId)?.color"
        closable
        @close="handleRemoveTag(tagId)"
      >
        {{ getTag(tagId)?.name }}
      </el-tag>
      
      <!-- 添加按钮 -->
      <el-button
        v-if="!inputVisible && selectedTags.length < max"
        size="small"
        @click="inputVisible = true"
      >
        + 添加标签
      </el-button>
      
      <!-- 输入框 -->
      <el-input
        v-if="inputVisible"
        v-model="newTagName"
        size="small"
        style="width: 120px"
        placeholder="标签名称"
        @blur="handleAddTag"
        @keyup.enter="handleAddTag"
      />
    </div>

    <!-- 标签建议 -->
    <div v-if="availableTags.length > 0" class="tag-suggestions">
      <div class="suggestions-header">常用标签：</div>
      <el-tag
        v-for="tag in availableTags.slice(0, 10)"
        :key="tag.id"
        :color="tag.color"
        :effect="selectedTags.includes(tag.id) ? 'dark' : 'plain'"
        size="small"
        style="cursor: pointer; margin: 4px"
        @click="!selectedTags.includes(tag.id) && selectedTags.push(tag.id)"
      >
        {{ tag.name }}
      </el-tag>
    </div>
  </div>
</template>

<style scoped lang="scss">
.tag-selector {
  .selected-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
  }
  
  .tag-suggestions {
    .suggestions-header {
      font-size: 13px;
      color: var(--text-secondary);
      margin-bottom: 8px;
    }
  }
}
</style>
```

### 2.5.2 TagCloud组件

**TagCloud.vue - 标签云可视化**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTagsStore } from '@/stores/tags'

interface Props {
  maxTags?: number
  minSize?: number
  maxSize?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxTags: 50,
  minSize: 12,
  maxSize: 32
})

const router = useRouter()
const tagsStore = useTagsStore()

// 标签数据
const tags = computed(() => {
  return tagsStore.tags
    .slice(0, props.maxTags)
    .sort((a, b) => b.use_count - a.use_count)
})

// 计算标签大小
const getTagSize = (useCount: number) => {
  if (tags.value.length === 0) return props.minSize
  
  const maxCount = Math.max(...tags.value.map(t => t.use_count))
  const minCount = Math.min(...tags.value.map(t => t.use_count))
  
  if (maxCount === minCount) return props.minSize
  
  const ratio = (useCount - minCount) / (maxCount - minCount)
  return props.minSize + ratio * (props.maxSize - props.minSize)
}

// 计算透明度
const getTagOpacity = (useCount: number) => {
  if (tags.value.length === 0) return 1
  
  const maxCount = Math.max(...tags.value.map(t => t.use_count))
  const minCount = Math.min(...tags.value.map(t => t.use_count))
  
  if (maxCount === minCount) return 1
  
  const ratio = (useCount - minCount) / (maxCount - minCount)
  return 0.5 + ratio * 0.5
}

// 点击标签
const handleTagClick = (tagId: number) => {
  router.push({ path: '/notes', query: { tag: tagId } })
}
</script>

<template>
  <div class="tag-cloud">
    <span
      v-for="tag in tags"
      :key="tag.id"
      class="tag-item"
      :style="{
        fontSize: `${getTagSize(tag.use_count)}px`,
        color: tag.color,
        opacity: getTagOpacity(tag.use_count)
      }"
      @click="handleTagClick(tag.id)"
    >
      {{ tag.name }}
    </span>
  </div>
</template>

<style scoped lang="scss">
.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  align-items: center;
  justify-content: center;
  padding: 32px;
  
  .tag-item {
    cursor: pointer;
    transition: all 0.3s ease;
    font-weight: 600;
    line-height: 1;
    
    &:hover {
      opacity: 1 !important;
      transform: scale(1.1);
      text-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
  }
}
</style>
```

---

## 2.6 多视图浏览

### 2.6.1 NoteCard组件（网格视图）

**NoteCard.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { Note } from '@/types/note'
import { formatDate } from '@/utils/format'

interface Props {
  note: Note
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'click'): void
}>()

// 媒体处理
const firstMedia = computed(() => {
  return props.note.media_files?.[0]
})

const hasMultipleMedia = computed(() => {
  return (props.note.media_files?.length || 0) > 1
})

// 文本摘要
const excerpt = computed(() => {
  const text = props.note.message_text || ''
  return text.length > 150 ? text.slice(0, 150) + '...' : text
})
</script>

<template>
  <div class="note-card" @click="emit('click')">
    <!-- 媒体预览 -->
    <div v-if="firstMedia" class="note-media">
      <img
        v-if="firstMedia.file_type === 'photo'"
        :src="`/media/${firstMedia.file_path}`"
        :alt="note.title"
        class="media-image"
      />
      <div v-else-if="firstMedia.file_type === 'video'" class="media-video">
        <img
          :src="`/media/${firstMedia.thumbnail_path}`"
          :alt="note.title"
          class="media-thumbnail"
        />
        <div class="video-badge">
          <el-icon><VideoPlay /></el-icon>
          视频
        </div>
      </div>
      
      <!-- 多媒体标记 -->
      <div v-if="hasMultipleMedia" class="multi-media-badge">
        +{{ note.media_files.length - 1 }}
      </div>
    </div>

    <!-- 卡片内容 -->
    <div class="note-content">
      <!-- 标题 -->
      <h3 v-if="note.title" class="note-title">
        {{ note.title }}
      </h3>
      
      <!-- 摘要 -->
      <p class="note-excerpt">
        {{ excerpt }}
      </p>
      
      <!-- 标签 -->
      <div v-if="note.tags && note.tags.length > 0" class="note-tags">
        <el-tag
          v-for="tag in note.tags.slice(0, 3)"
          :key="tag.id"
          :color="tag.color"
          size="small"
        >
          {{ tag.name }}
        </el-tag>
      </div>
    </div>

    <!-- 卡片底部 -->
    <div class="note-footer">
      <div class="note-meta">
        <span class="meta-item">
          <el-icon><Clock /></el-icon>
          {{ formatDate(note.timestamp) }}
        </span>
        <span v-if="note.source_name" class="meta-item">
          <el-icon><Location /></el-icon>
          {{ note.source_name }}
        </span>
      </div>
      
      <div class="note-actions">
        <el-button
          :icon="note.is_favorite ? StarFilled : Star"
          text
          @click.stop="$emit('toggle-favorite', note.id)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.note-card {
  background-color: var(--bg-secondary);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s ease;
  border: 1px solid var(--border-color);
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
  }
}

.note-media {
  position: relative;
  width: 100%;
  height: 200px;
  background-color: var(--bg-hover);
  overflow: hidden;
  
  .media-image,
  .media-thumbnail {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  
  .video-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .multi-media-badge {
    position: absolute;
    bottom: 12px;
    right: 12px;
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
  }
}

.note-content {
  padding: 16px;
  
  .note-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .note-excerpt {
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-secondary);
    margin-bottom: 12px;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  .note-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
}

.note-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-top: 1px solid var(--border-color);
  
  .note-meta {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: var(--text-secondary);
    
    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }
  }
}
</style>
```

### 2.6.2 NoteList组件（列表视图）

**NoteList.vue**

```vue
<script setup lang="ts">
import type { Note } from '@/types/note'
import { formatDate } from '@/utils/format'

interface Props {
  notes: Note[]
}

defineProps<Props>()
const emit = defineEmits<{
  (e: 'note-click', id: number): void
}>()
</script>

<template>
  <div class="note-list">
    <div
      v-for="note in notes"
      :key="note.id"
      class="note-list-item"
      @click="emit('note-click', note.id)"
    >
      <!-- 左侧缩略图 -->
      <div v-if="note.media_files?.[0]" class="item-thumbnail">
        <img
          :src="`/media/${note.media_files[0].thumbnail_path || note.media_files[0].file_path}`"
          :alt="note.title"
        />
      </div>
      <div v-else class="item-thumbnail placeholder">
        <el-icon><Document /></el-icon>
      </div>

      <!-- 中间内容 -->
      <div class="item-content">
        <h3 class="item-title">
          {{ note.title || '无标题' }}
        </h3>
        <p class="item-excerpt">
          {{ note.message_text?.slice(0, 200) }}
        </p>
        <div class="item-meta">
          <span class="meta-item">
            <el-icon><Clock /></el-icon>
            {{ formatDate(note.timestamp) }}
          </span>
          <span class="meta-item">
            <el-icon><Location /></el-icon>
            {{ note.source_name }}
          </span>
          <span v-if="note.view_count" class="meta-item">
            <el-icon><View /></el-icon>
            {{ note.view_count }}
          </span>
        </div>
      </div>

      <!-- 右侧操作 -->
      <div class="item-actions">
        <el-button
          :icon="note.is_favorite ? StarFilled : Star"
          text
          @click.stop
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.note-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.note-list-item {
  display: flex;
  gap: 16px;
  padding: 16px;
  background-color: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    transform: translateX(4px);
  }
}

.item-thumbnail {
  width: 120px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  background-color: var(--bg-hover);
  
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  
  &.placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 32px;
    color: var(--text-secondary);
  }
}

.item-content {
  flex: 1;
  min-width: 0;
  
  .item-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .item-excerpt {
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-secondary);
    margin-bottom: 12px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  .item-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 12px;
    color: var(--text-secondary);
    
    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }
  }
}

.item-actions {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}
</style>
```

### 2.6.3 NoteTimeline组件（时间线视图）

**NoteTimeline.vue**

```vue
<script setup lang="ts">
import { computed } from 'vue'
import type { Note } from '@/types/note'
import { formatDate } from '@/utils/format'
import dayjs from 'dayjs'

interface Props {
  notes: Note[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'note-click', id: number): void
}>()

// 按日期分组
const groupedNotes = computed(() => {
  const groups: Record<string, Note[]> = {}
  
  props.notes.forEach(note => {
    const date = dayjs(note.timestamp).format('YYYY-MM-DD')
    if (!groups[date]) {
      groups[date] = []
    }
    groups[date].push(note)
  })
  
  return Object.entries(groups).map(([date, notes]) => ({
    date,
    displayDate: formatTimelineDate(date),
    notes
  }))
})

const formatTimelineDate = (date: string) => {
  const d = dayjs(date)
  const today = dayjs()
  const yesterday = today.subtract(1, 'day')
  
  if (d.isSame(today, 'day')) {
    return '今天'
  } else if (d.isSame(yesterday, 'day')) {
    return '昨天'
  } else if (d.isSame(today, 'year')) {
    return d.format('M月D日')
  } else {
    return d.format('YYYY年M月D日')
  }
}
</script>

<template>
  <div class="note-timeline">
    <div
      v-for="group in groupedNotes"
      :key="group.date"
      class="timeline-group"
    >
      <!-- 日期标题 -->
      <div class="timeline-date">
        <div class="date-marker" />
        <h3 class="date-text">{{ group.displayDate }}</h3>
        <div class="date-line" />
      </div>

      <!-- 笔记列表 -->
      <div class="timeline-items">
        <div
          v-for="note in group.notes"
          :key="note.id"
          class="timeline-item"
          @click="emit('note-click', note.id)"
        >
          <div class="item-time">
            {{ dayjs(note.timestamp).format('HH:mm') }}
          </div>
          
          <div class="item-content">
            <div class="item-header">
              <h4 class="item-title">{{ note.title || '无标题' }}</h4>
              <span class="item-source">{{ note.source_name }}</span>
            </div>
            
            <p v-if="note.message_text" class="item-text">
              {{ note.message_text.slice(0, 150) }}
            </p>
            
            <div v-if="note.media_files && note.media_files.length > 0" class="item-media">
              <img
                v-for="media in note.media_files.slice(0, 3)"
                :key="media.id"
                :src="`/media/${media.thumbnail_path || media.file_path}`"
                :alt="note.title"
              />
            </div>
            
            <div v-if="note.tags && note.tags.length > 0" class="item-tags">
              <el-tag
                v-for="tag in note.tags"
                :key="tag.id"
                :color="tag.color"
                size="small"
              >
                {{ tag.name }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.note-timeline {
  position: relative;
  padding: 20px 0;
}

.timeline-group {
  margin-bottom: 48px;
  
  &:last-child {
    margin-bottom: 0;
  }
}

.timeline-date {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
  
  .date-marker {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    flex-shrink: 0;
  }
  
  .date-text {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
  }
  
  .date-line {
    flex: 1;
    height: 2px;
    background: linear-gradient(
      to right,
      var(--border-color) 0%,
      transparent 100%
    );
  }
}

.timeline-items {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-left: 32px;
  border-left: 2px solid var(--border-color);
}

.timeline-item {
  display: flex;
  gap: 16px;
  cursor: pointer;
  transition: all 0.3s;
  
  &:hover {
    .item-content {
      box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
      transform: translateX(4px);
    }
  }
  
  .item-time {
    width: 60px;
    font-size: 13px;
    color: var(--text-secondary);
    font-weight: 600;
    flex-shrink: 0;
    padding-top: 4px;
  }
  
  .item-content {
    flex: 1;
    background-color: var(--bg-secondary);
    border-radius: 8px;
    padding: 16px;
    border: 1px solid var(--border-color);
    transition: all 0.3s;
    
    .item-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      
      .item-title {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
      }
      
      .item-source {
        font-size: 12px;
        color: var(--text-secondary);
        background-color: var(--bg-hover);
        padding: 4px 10px;
        border-radius: 12px;
      }
    }
    
    .item-text {
      font-size: 14px;
      line-height: 1.6;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }
    
    .item-media {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-bottom: 12px;
      
      img {
        width: 100%;
        height: 80px;
        object-fit: cover;
        border-radius: 6px;
      }
    }
    
    .item-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
  }
}
</style>
```

---

## 2.7 批量操作设计

### 2.7.1 多选机制

**Composable: useSelection.ts**

```typescript
// composables/useSelection.ts
import { ref, computed } from 'vue'

export function useSelection<T extends { id: number }>(items: Ref<T[]>) {
  const selectedIds = ref<Set<number>>(new Set())
  const selectMode = ref(false)
  
  // 全选状态
  const isAllSelected = computed(() => {
    return items.value.length > 0 && 
           selectedIds.value.size === items.value.length
  })
  
  const isIndeterminate = computed(() => {
    return selectedIds.value.size > 0 && 
           selectedIds.value.size < items.value.length
  })
  
  // 切换选择模式
  const toggleSelectMode = () => {
    selectMode.value = !selectMode.value
    if (!selectMode.value) {
      clearSelection()
    }
  }
  
  // 全选/取消全选
  const toggleSelectAll = () => {
    if (isAllSelected.value) {
      clearSelection()
    } else {
      items.value.forEach(item => selectedIds.value.add(item.id))
    }
  }
  
  // 切换单个项目
  const toggleItem = (id: number) => {
    if (selectedIds.value.has(id)) {
      selectedIds.value.delete(id)
    } else {
      selectedIds.value.add(id)
    }
  }
  
  // 清除选择
  const clearSelection = () => {
    selectedIds.value.clear()
  }
  
  // 是否选中
  const isSelected = (id: number) => {
    return selectedIds.value.has(id)
  }
  
  // 获取选中的项目
  const selectedItems = computed(() => {
    return items.value.filter(item => selectedIds.value.has(item.id))
  })
  
  return {
    selectedIds: computed(() => Array.from(selectedIds.value)),
    selectedCount: computed(() => selectedIds.value.size),
    selectedItems,
    selectMode,
    isAllSelected,
    isIndeterminate,
    toggleSelectMode,
    toggleSelectAll,
    toggleItem,
    clearSelection,
    isSelected
  }
}
```

### 2.7.2 批量操作UI

**BatchActionsBar.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

interface Props {
  selectedCount: number
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'delete'): void
  (e: 'addTags'): void
  (e: 'export'): void
  (e: 'archive'): void
  (e: 'cancel'): void
}>()

const confirmDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${props.selectedCount} 条笔记吗？此操作不可恢复。`,
      '批量删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    emit('delete')
  } catch {
    // 用户取消
  }
}
</script>

<template>
  <transition name="slide-up">
    <div v-if="selectedCount > 0" class="batch-actions-bar">
      <div class="actions-left">
        <span class="selected-count">
          已选择 <strong>{{ selectedCount }}</strong> 项
        </span>
      </div>
      
      <div class="actions-center">
        <el-button @click="emit('addTags')">
          <el-icon><PriceTag /></el-icon>
          添加标签
        </el-button>
        
        <el-button @click="emit('archive')">
          <el-icon><FolderAdd /></el-icon>
          归档
        </el-button>
        
        <el-button @click="emit('export')">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        
        <el-button type="danger" @click="confirmDelete">
          <el-icon><Delete /></el-icon>
          删除
        </el-button>
      </div>
      
      <div class="actions-right">
        <el-button text @click="emit('cancel')">
          取消
        </el-button>
      </div>
    </div>
  </transition>
</template>

<style scoped lang="scss">
.batch-actions-bar {
  position: fixed;
  bottom: 0;
  left: 260px;
  right: 0;
  height: 70px;
  background-color: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  z-index: 999;
  
  .actions-left {
    .selected-count {
      font-size: 15px;
      color: var(--text-secondary);
      
      strong {
        color: var(--primary-color);
        font-weight: 600;
      }
    }
  }
  
  .actions-center {
    display: flex;
    gap: 12px;
  }
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform 0.3s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(100%);
}
</style>
```

---

## 2.8 移动端适配

### 2.8.1 响应式断点设计

```scss
// styles/variables.scss

// 断点定义
$breakpoint-xs: 480px;   // 超小屏幕（手机竖屏）
$breakpoint-sm: 768px;   // 小屏幕（平板竖屏）
$breakpoint-md: 1024px;  // 中等屏幕（平板横屏）
$breakpoint-lg: 1280px;  // 大屏幕（笔记本）
$breakpoint-xl: 1920px;  // 超大屏幕（台式机）

// Mixins
@mixin xs {
  @media (max-width: #{$breakpoint-xs}) {
    @content;
  }
}

@mixin sm {
  @media (max-width: #{$breakpoint-sm}) {
    @content;
  }
}

@mixin md {
  @media (max-width: #{$breakpoint-md}) {
    @content;
  }
}

@mixin lg {
  @media (max-width: #{$breakpoint-lg}) {
    @content;
  }
}

@mixin xl {
  @media (min-width: #{$breakpoint-xl}) {
    @content;
  }
}
```

### 2.8.2 移动端导航

**MobileNav.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const drawerVisible = ref(false)
const activeTab = ref('notes')

const menuItems = [
  { id: 'notes', label: '笔记', icon: 'Document', path: '/notes' },
  { id: 'search', label: '搜索', icon: 'Search', path: '/search' },
  { id: 'tags', label: '标签', icon: 'PriceTag', path: '/tags' },
  { id: 'settings', label: '设置', icon: 'Setting', path: '/settings' },
]

const navigateTo = (path: string, id: string) => {
  activeTab.value = id
  router.push(path)
  drawerVisible.value = false
}
</script>

<template>
  <div class="mobile-nav">
    <!-- 顶部栏 -->
    <div class="mobile-header">
      <button class="menu-btn" @click="drawerVisible = true">
        <el-icon><Menu /></el-icon>
      </button>
      <h1 class="app-title">Telegram Notes</h1>
      <button class="user-btn">
        <el-avatar :size="32">{{ authStore.username[0] }}</el-avatar>
      </button>
    </div>

    <!-- 侧边抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="80%"
    >
      <div class="drawer-content">
        <div class="drawer-header">
          <el-avatar :size="60">{{ authStore.username[0] }}</el-avatar>
          <div class="user-info">
            <h3>{{ authStore.username }}</h3>
            <p>管理员</p>
          </div>
        </div>
        
        <nav class="drawer-nav">
          <div
            v-for="item in menuItems"
            :key="item.id"
            :class="['nav-item', { active: activeTab === item.id }]"
            @click="navigateTo(item.path, item.id)"
          >
            <el-icon class="nav-icon">
              <component :is="item.icon" />
            </el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </div>
        </nav>
        
        <div class="drawer-footer">
          <el-button type="danger" @click="authStore.logout()">
            登出
          </el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 底部标签栏 -->
    <div class="mobile-tabbar">
      <div
        v-for="item in menuItems.slice(0, 4)"
        :key="item.id"
        :class="['tab-item', { active: activeTab === item.id }]"
        @click="navigateTo(item.path, item.id)"
      >
        <el-icon class="tab-icon">
          <component :is="item.icon" />
        </el-icon>
        <span class="tab-label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.mobile-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  z-index: 1000;
  
  .menu-btn,
  .user-btn {
    background: none;
    border: none;
    padding: 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
  }
  
  .app-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
  }
}

.drawer-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  
  .drawer-header {
    padding: 32px 24px;
    display: flex;
    gap: 16px;
    align-items: center;
    border-bottom: 1px solid var(--border-color);
    
    .user-info {
      h3 {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 4px;
      }
      
      p {
        font-size: 14px;
        color: var(--text-secondary);
      }
    }
  }
  
  .drawer-nav {
    flex: 1;
    padding: 16px 0;
    
    .nav-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 16px 24px;
      cursor: pointer;
      transition: background-color 0.2s;
      
      .nav-icon {
        font-size: 24px;
        color: var(--text-secondary);
      }
      
      .nav-label {
        font-size: 16px;
        color: var(--text-primary);
      }
      
      &.active {
        background-color: var(--primary-light);
        
        .nav-icon,
        .nav-label {
          color: var(--primary-color);
        }
      }
      
      &:active {
        background-color: var(--bg-hover);
      }
    }
  }
  
  .drawer-footer {
    padding: 24px;
    border-top: 1px solid var(--border-color);
  }
}

.mobile-tabbar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background-color: var(--bg-secondary);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: space-around;
  align-items: center;
  z-index: 1000;
  
  .tab-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    cursor: pointer;
    transition: all 0.2s;
    
    .tab-icon {
      font-size: 24px;
      color: var(--text-secondary);
    }
    
    .tab-label {
      font-size: 11px;
      color: var(--text-secondary);
    }
    
    &.active {
      .tab-icon,
      .tab-label {
        color: var(--primary-color);
      }
    }
    
    &:active {
      transform: scale(0.95);
    }
  }
}
</style>
```

---

## 2.9 设计系统

### 2.9.1 色彩系统

```scss
// styles/variables.scss

// 主色
$primary: #667eea;
$primary-light: #e0e7ff;
$primary-dark: #5568d3;

// 功能色
$success: #10b981;
$warning: #f59e0b;
$danger: #ef4444;
$info: #3b82f6;

// 中性色 - 浅色模式
$gray-50: #f9fafb;
$gray-100: #f3f4f6;
$gray-200: #e5e7eb;
$gray-300: #d1d5db;
$gray-400: #9ca3af;
$gray-500: #6b7280;
$gray-600: #4b5563;
$gray-700: #374151;
$gray-800: #1f2937;
$gray-900: #111827;

// 中性色 - 深色模式
$dark-bg-primary: #0f0f0f;
$dark-bg-secondary: #1a1a1a;
$dark-bg-tertiary: #2d2d2d;
$dark-text-primary: #ffffff;
$dark-text-secondary: #b0b0b0;
$dark-border: #404040;

// CSS变量定义
:root {
  // 主题色
  --primary-color: #{$primary};
  --primary-light: #{$primary-light};
  --primary-dark: #{$primary-dark};
  
  // 功能色
  --success-color: #{$success};
  --warning-color: #{$warning};
  --danger-color: #{$danger};
  --info-color: #{$info};
  
  // 浅色模式
  --bg-primary: #{$gray-50};
  --bg-secondary: #ffffff;
  --bg-tertiary: #{$gray-100};
  --bg-hover: #{$gray-100};
  --text-primary: #{$gray-900};
  --text-secondary: #{$gray-600};
  --text-tertiary: #{$gray-400};
  --border-color: #{$gray-200};
  
  // 阴影
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  
  // 圆角
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;
  
  // 间距
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
  --spacing-2xl: 48px;
}

// 深色模式
.theme-dark {
  --bg-primary: #{$dark-bg-primary};
  --bg-secondary: #{$dark-bg-secondary};
  --bg-tertiary: #{$dark-bg-tertiary};
  --bg-hover: #{$dark-bg-tertiary};
  --text-primary: #{$dark-text-primary};
  --text-secondary: #{$dark-text-secondary};
  --text-tertiary: #{$gray-500};
  --border-color: #{$dark-border};
}
```

### 2.9.2 排版系统

```scss
// styles/typography.scss

// 字体家族
$font-family-base: 'Inter', 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
$font-family-mono: 'Fira Code', 'Consolas', 'Monaco', monospace;

// 字体大小
$font-size-xs: 11px;
$font-size-sm: 13px;
$font-size-base: 15px;
$font-size-lg: 17px;
$font-size-xl: 20px;
$font-size-2xl: 24px;
$font-size-3xl: 32px;
$font-size-4xl: 40px;

// 字重
$font-weight-light: 300;
$font-weight-normal: 400;
$font-weight-medium: 500;
$font-weight-semibold: 600;
$font-weight-bold: 700;

// 行高
$line-height-tight: 1.3;
$line-height-normal: 1.5;
$line-height-relaxed: 1.7;
$line-height-loose: 2;

// 应用
body {
  font-family: $font-family-base;
  font-size: $font-size-base;
  line-height: $line-height-normal;
  color: var(--text-primary);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

h1 {
  font-size: $font-size-4xl;
  font-weight: $font-weight-bold;
  line-height: $line-height-tight;
}

h2 {
  font-size: $font-size-3xl;
  font-weight: $font-weight-bold;
  line-height: $line-height-tight;
}

h3 {
  font-size: $font-size-2xl;
  font-weight: $font-weight-semibold;
  line-height: $line-height-tight;
}

h4 {
  font-size: $font-size-xl;
  font-weight: $font-weight-semibold;
  line-height: $line-height-normal;
}

code {
  font-family: $font-family-mono;
  font-size: 0.9em;
}
```

### 2.9.3 组件库规范

```scss
// styles/components.scss

// 按钮
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font-size: $font-size-base;
  font-weight: $font-weight-medium;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    transform: translateY(-1px);
  }
  
  &:active {
    transform: translateY(0);
  }
  
  &.btn-primary {
    background: linear-gradient(135deg, $primary 0%, $primary-dark 100%);
    color: white;
    
    &:hover {
      box-shadow: 0 6px 16px rgba($primary, 0.3);
    }
  }
  
  &.btn-secondary {
    background-color: var(--bg-tertiary);
    color: var(--text-primary);
    
    &:hover {
      background-color: var(--bg-hover);
    }
  }
  
  &.btn-danger {
    background-color: $danger;
    color: white;
    
    &:hover {
      box-shadow: 0 6px 16px rgba($danger, 0.3);
    }
  }
  
  &.btn-sm {
    padding: 6px 14px;
    font-size: $font-size-sm;
  }
  
  &.btn-lg {
    padding: 14px 28px;
    font-size: $font-size-lg;
  }
}

// 输入框
.input {
  width: 100%;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: $font-size-base;
  color: var(--text-primary);
  background-color: var(--bg-secondary);
  transition: all 0.2s;
  
  &:focus {
    outline: none;
    border-color: $primary;
    box-shadow: 0 0 0 3px rgba($primary, 0.1);
  }
  
  &::placeholder {
    color: var(--text-tertiary);
  }
}

// 卡片
.card {
  background-color: var(--bg-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  padding: var(--spacing-lg);
  transition: all 0.3s ease;
  
  &:hover {
    box-shadow: var(--shadow-lg);
  }
}

// 标签
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: $font-size-sm;
  font-weight: $font-weight-medium;
  
  &.tag-primary {
    background-color: $primary-light;
    color: $primary;
  }
  
  &.tag-success {
    background-color: rgba($success, 0.1);
    color: $success;
  }
}
```

### 2.9.4 动画和过渡规范

```scss
// styles/transitions.scss

// 缓动函数
$ease-in: cubic-bezier(0.4, 0, 1, 1);
$ease-out: cubic-bezier(0, 0, 0.2, 1);
$ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
$ease-bounce: cubic-bezier(0.68, -0.55, 0.265, 1.55);

// 持续时间
$duration-fast: 150ms;
$duration-normal: 250ms;
$duration-slow: 350ms;

// 淡入淡出
.fade-enter-active,
.fade-leave-active {
  transition: opacity $duration-normal $ease-in-out;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// 滑动
.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform $duration-normal $ease-out;
}

.slide-up-enter-from,
.slide-up-leave-to {
  transform: translateY(20px);
}

// 缩放
.zoom-enter-active,
.zoom-leave-active {
  transition: transform $duration-normal $ease-bounce, 
              opacity $duration-normal $ease-in-out;
}

.zoom-enter-from,
.zoom-leave-to {
  transform: scale(0.95);
  opacity: 0;
}

// 列表过渡
.list-enter-active,
.list-leave-active {
  transition: all $duration-normal $ease-in-out;
}

.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

.list-move {
  transition: transform $duration-normal $ease-in-out;
}

// 骨架屏动画
@keyframes skeleton-loading {
  0% {
    background-position: -200px 0;
  }
  100% {
    background-position: calc(200px + 100%) 0;
  }
}

.skeleton {
  background: linear-gradient(
    90deg,
    var(--bg-tertiary) 0%,
    var(--bg-hover) 50%,
    var(--bg-tertiary) 100%
  );
  background-size: 200px 100%;
  animation: skeleton-loading 1.5s infinite;
}
```

---

**继续编写中...**

本部分已完成：
- ✅ 2.4 搜索和高级筛选（完整）
- ✅ 2.5 标签和分类系统
- ✅ 2.6 多视图浏览
- ✅ 2.7 批量操作设计
- ✅ 2.8 移动端适配
- ✅ 2.9 设计系统

下一部分将继续编写第三部分：技术实施方案。
