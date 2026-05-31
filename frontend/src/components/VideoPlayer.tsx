import { useRef } from 'react'

interface VideoPlayerProps {
  videoUrl: string
}

export default function VideoPlayer({ videoUrl }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  const handleDownload = () => {
    const a = document.createElement('a')
    a.href = videoUrl
    a.download = `digital-human-${Date.now()}.mp4`
    a.click()
  }

  return (
    <div className="bg-[#1a1d2e] rounded-2xl overflow-hidden border border-white/5">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-300">视频预览</h3>
        <button
          type="button"
          onClick={handleDownload}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/10 text-purple-400 text-sm hover:bg-purple-500/20 transition-all"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          下载视频
        </button>
      </div>
      <video
        ref={videoRef}
        src={videoUrl}
        controls
        className="w-full aspect-video bg-black"
        autoPlay
      />
    </div>
  )
}
