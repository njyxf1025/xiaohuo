import { useState, useRef, useCallback } from 'react'
import { uploadMusic } from '../api/client'

const ACCEPTED_FORMATS = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp4', 'audio/x-m4a', 'audio/flac', 'audio/x-flac']
const ACCEPTED_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.flac']

interface MusicUploadProps {
  onComplete: (fileId: string, filename: string, duration: number) => void
}

export default function MusicUpload({ onComplete }: MusicUploadProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [fileInfo, setFileInfo] = useState<{ name: string; size: string } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const validateFile = (file: File): boolean => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_FORMATS.includes(file.type) && !ACCEPTED_EXTENSIONS.includes(ext)) {
      setError('不支持的格式，请上传 MP3/WAV/M4A/FLAC 文件')
      return false
    }
    if (file.size > 100 * 1024 * 1024) {
      setError('文件大小不能超过 100MB')
      return false
    }
    return true
  }

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const handleFile = useCallback(async (file: File) => {
    setError(null)
    if (!validateFile(file)) return

    setUploading(true)
    setProgress(0)
    setFileInfo({ name: file.name, size: formatSize(file.size) })

    try {
      const result = await uploadMusic(file, (p) => setProgress(p))
      setProgress(100)
      setTimeout(() => {
        onComplete(result.fileId, result.filename, result.duration)
      }, 500)
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败')
      setFileInfo(null)
    } finally {
      setUploading(false)
    }
  }, [onComplete])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }, [handleFile])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setIsDragging(false)
  }, [])

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }, [handleFile])

  return (
    <div className="max-w-xl mx-auto">
      <h2 className="text-xl font-bold text-gray-100 mb-6 text-center">上传音乐文件</h2>

      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`relative cursor-pointer rounded-2xl border-2 border-dashed p-12 text-center transition-all duration-300 ${
          isDragging
            ? 'border-purple-400 bg-purple-500/10 scale-[1.02]'
            : uploading
              ? 'border-blue-400/30 bg-blue-500/5'
              : 'border-white/10 bg-[#1a1d2e] hover:border-purple-400/50 hover:bg-purple-500/5'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.flac,audio/*"
          onChange={handleChange}
          className="hidden"
        />

        {uploading ? (
          <div className="space-y-4">
            <div className="text-4xl">⏳</div>
            <p className="text-gray-300 font-medium">上传中...</p>
            <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-gray-500">{progress}%</p>
          </div>
        ) : fileInfo ? (
          <div className="space-y-2">
            <div className="text-4xl">✅</div>
            <p className="text-gray-200 font-medium">{fileInfo.name}</p>
            <p className="text-sm text-gray-500">{fileInfo.size}</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-5xl">🎵</div>
            <p className="text-gray-300 font-medium">拖拽音乐文件到此处</p>
            <p className="text-sm text-gray-500">或点击选择文件</p>
            <p className="text-xs text-gray-600 mt-2">支持 MP3 / WAV / M4A / FLAC，最大 100MB</p>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
          {error}
        </div>
      )}
    </div>
  )
}
