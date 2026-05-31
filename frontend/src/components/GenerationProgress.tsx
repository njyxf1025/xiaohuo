import { useEffect, useState, useRef } from 'react'
import { getGenerationStatus } from '../api/client'

interface GenerationProgressProps {
  taskId: string
  onComplete: (videoUrl: string) => void
}

const stepMessages: Record<string, string> = {
  pending: '排队中，请稍候...',
  processing: '正在生成视频...',
  completed: '生成完成！',
  failed: '生成失败',
}

export default function GenerationProgress({ taskId, onComplete }: GenerationProgressProps) {
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<'pending' | 'processing' | 'completed' | 'failed'>('pending')
  const [step, setStep] = useState('')
  const intervalRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    intervalRef.current = window.setInterval(async () => {
      try {
        const result = await getGenerationStatus(taskId)
        setProgress(result.progress)
        setStatus(result.status)
        setStep(result.step)

        if (result.status === 'completed' && result.videoUrl) {
          window.clearInterval(intervalRef.current)
          onComplete(result.videoUrl)
        }
        if (result.status === 'failed') {
          window.clearInterval(intervalRef.current)
        }
      } catch {
        window.clearInterval(intervalRef.current)
        setStatus('failed')
        setStep('网络错误')
      }
    }, 2000)

    return () => window.clearInterval(intervalRef.current)
  }, [taskId, onComplete])

  return (
    <div className="bg-[#1a1d2e] rounded-2xl p-8 border border-white/5">
      <h2 className="text-xl font-bold text-gray-100 mb-6 text-center">视频生成中</h2>

      <div className="max-w-md mx-auto space-y-4">
        <div className="relative h-3 bg-white/5 rounded-full overflow-hidden">
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
          <div
            className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-500 to-blue-500 rounded-full transition-all duration-500 animate-pulse opacity-30"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className={`font-medium ${
            status === 'completed' ? 'text-green-400' :
            status === 'failed' ? 'text-red-400' :
            'text-purple-400'
          }`}>
            {stepMessages[status]}
          </span>
          <span className="text-gray-500 font-mono">{progress}%</span>
        </div>

        {step && status === 'processing' && (
          <p className="text-xs text-gray-500 text-center">{step}</p>
        )}

        {status === 'pending' && (
          <div className="flex items-center justify-center gap-2 text-gray-500">
            <div className="w-3 h-3 border border-gray-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">排队等待中</span>
          </div>
        )}

        {status === 'failed' && (
          <div className="text-center">
            <p className="text-red-400 text-sm mb-2">生成失败，请重试</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-red-500/10 text-red-400 text-sm hover:bg-red-500/20 transition-all"
            >
              重新开始
            </button>
          </div>
        )}

        {status === 'completed' && (
          <div className="text-center">
            <div className="text-4xl mb-2">🎉</div>
            <p className="text-green-400 font-medium">视频生成完成！</p>
          </div>
        )}
      </div>
    </div>
  )
}
