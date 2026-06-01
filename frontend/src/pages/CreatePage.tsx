import { useState } from 'react'
import MusicUpload from '../components/MusicUpload'
import AudioWaveform from '../components/AudioWaveform'
import AvatarSelector from '../components/AvatarSelector'
import ModelSelector from '../components/ModelSelector'
import GenerationProgress from '../components/GenerationProgress'
import VideoPlayer from '../components/VideoPlayer'
import { generateVideo } from '../api/client'

type Step = 'upload' | 'waveform' | 'avatar' | 'generate'

export default function CreatePage() {
  const [currentStep, setCurrentStep] = useState<Step>('upload')
  const [musicFileId, setMusicFileId] = useState<string>('')
  const [musicFilename, setMusicFilename] = useState<string>('')
  const [musicDuration, setMusicDuration] = useState<number>(0)
  const [startTime, setStartTime] = useState<number>(0)
  const [endTime, setEndTime] = useState<number>(0)
  const [avatarId, setAvatarId] = useState<string>('')
  const [model, setModel] = useState<string>('wav2lip')
  const [taskId, setTaskId] = useState<string>('')
  const [videoUrl, setVideoUrl] = useState<string>('')
  const [isGenerating, setIsGenerating] = useState(false)

  const steps: { key: Step; label: string; icon: string }[] = [
    { key: 'upload', label: '上传音乐', icon: '🎵' },
    { key: 'waveform', label: '选择区间', icon: '🎶' },
    { key: 'avatar', label: '形象 & 模型', icon: '🧑‍🎤' },
    { key: 'generate', label: '生成视频', icon: '🎬' },
  ]

  const stepIndex = steps.findIndex((s) => s.key === currentStep)

  const handleUploadComplete = (fileId: string, filename: string, duration: number) => {
    setMusicFileId(fileId)
    setMusicFilename(filename)
    setMusicDuration(duration)
    setEndTime(duration)
    setCurrentStep('waveform')
  }

  const handleRegionConfirm = (start: number, end: number) => {
    setStartTime(start)
    setEndTime(end)
    setCurrentStep('avatar')
  }

  const handleStartGenerate = async () => {
    if (!musicFileId || !avatarId) return
    setIsGenerating(true)
    try {
      const result = await generateVideo({
        musicFileId,
        avatarId,
        model,
        startTime,
        endTime,
      })
      setTaskId(result.taskId)
      setCurrentStep('generate')
    } catch {
      alert('生成请求失败，请重试')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleGenerationComplete = (url: string) => {
    setVideoUrl(url)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-center gap-1 sm:gap-2 mb-10 overflow-x-auto px-2">
        {steps.map((step, i) => (
          <div key={step.key} className="flex items-center shrink-0">
            <button
              type="button"
              onClick={() => {
                if (i < stepIndex || (i === stepIndex)) {
                  setCurrentStep(step.key)
                }
              }}
              className={`flex items-center gap-1 sm:gap-2 px-2.5 sm:px-4 py-2 rounded-full text-sm font-medium transition-all duration-300 ${
                step.key === currentStep
                  ? 'bg-purple-500/20 text-purple-300 shadow-lg shadow-purple-500/10'
                  : i < stepIndex
                    ? 'bg-white/5 text-gray-300 hover:bg-white/10'
                    : 'text-gray-600'
              }`}
            >
              <span>{step.icon}</span>
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {i < steps.length - 1 && (
              <div className={`w-4 sm:w-12 h-0.5 mx-0.5 sm:mx-1 rounded ${i < stepIndex ? 'bg-purple-500/50' : 'bg-white/10'}`} />
            )}
          </div>
        ))}
      </div>

      <div className="transition-all duration-500">
        {currentStep === 'upload' && (
          <div className="animate-fadeIn">
            <MusicUpload onComplete={handleUploadComplete} />
          </div>
        )}

        {currentStep === 'waveform' && musicFileId && (
          <div className="animate-fadeIn">
            <AudioWaveform
              fileId={musicFileId}
              filename={musicFilename}
              duration={musicDuration}
              onRegionConfirm={handleRegionConfirm}
              onBack={() => setCurrentStep('upload')}
            />
          </div>
        )}

        {currentStep === 'avatar' && (
          <div className="animate-fadeIn space-y-8">
            <AvatarSelector selectedId={avatarId} onSelect={setAvatarId} />
            <ModelSelector selected={model} onSelect={setModel} />
            <div className="flex items-center justify-between pt-4">
              <button
                type="button"
                onClick={() => setCurrentStep('waveform')}
                className="px-6 py-2.5 rounded-xl text-gray-400 hover:text-gray-200 hover:bg-white/5 transition-all"
              >
                ← 返回
              </button>
              <button
                type="button"
                onClick={handleStartGenerate}
                disabled={!avatarId || isGenerating}
                className="px-8 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 transition-all duration-300"
              >
                {isGenerating ? '提交中...' : '开始生成 🚀'}
              </button>
            </div>
          </div>
        )}

        {currentStep === 'generate' && taskId && (
          <div className="animate-fadeIn space-y-8">
            <GenerationProgress taskId={taskId} onComplete={handleGenerationComplete} />
            {videoUrl && <VideoPlayer videoUrl={videoUrl} />}
          </div>
        )}
      </div>
    </div>
  )
}
