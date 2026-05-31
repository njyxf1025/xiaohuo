import { useEffect, useState, useCallback } from 'react'
import { getAvatarList, uploadAvatar } from '../api/client'

interface Avatar {
  id: string
  name: string
  thumbnail: string
}

interface AvatarSelectorProps {
  selectedId: string
  onSelect: (id: string) => void
}

export default function AvatarSelector({ selectedId, onSelect }: AvatarSelectorProps) {
  const [avatars, setAvatars] = useState<Avatar[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    getAvatarList()
      .then(setAvatars)
      .catch(() => setAvatars([]))
      .finally(() => setLoading(false))
  }, [])

  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const avatar = await uploadAvatar(file)
      setAvatars((prev) => [...prev, avatar])
      onSelect(avatar.id)
    } catch {
      alert('上传失败')
    } finally {
      setUploading(false)
    }
  }, [onSelect])

  return (
    <div>
      <h2 className="text-xl font-bold text-gray-100 mb-4">选择数字人形象</h2>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
          {avatars.map((avatar) => (
            <button
              key={avatar.id}
              type="button"
              onClick={() => onSelect(avatar.id)}
              className={`group relative rounded-xl overflow-hidden border-2 transition-all duration-300 hover:-translate-y-0.5 ${
                selectedId === avatar.id
                  ? 'border-purple-500 shadow-lg shadow-purple-500/20'
                  : 'border-white/5 hover:border-white/20'
              }`}
            >
              <div className="aspect-square bg-[#1a1d2e]">
                <img
                  src={avatar.thumbnail}
                  alt={avatar.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="p-2 bg-[#1a1d2e]">
                <p className="text-xs text-gray-300 truncate">{avatar.name}</p>
              </div>
              {selectedId === avatar.id && (
                <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center">
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </button>
          ))}

          <label className="group relative rounded-xl overflow-hidden border-2 border-dashed border-white/10 hover:border-purple-400/50 transition-all duration-300 cursor-pointer hover:-translate-y-0.5">
            <div className="aspect-square bg-[#1a1d2e] flex flex-col items-center justify-center gap-2">
              {uploading ? (
                <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <svg className="w-8 h-8 text-gray-600 group-hover:text-purple-400 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                  </svg>
                  <span className="text-xs text-gray-600 group-hover:text-purple-400 transition-colors">自定义上传</span>
                </>
              )}
            </div>
            <input
              type="file"
              accept="image/*"
              onChange={handleUpload}
              className="hidden"
            />
          </label>
        </div>
      )}
    </div>
  )
}
