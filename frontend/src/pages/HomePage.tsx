import { Link } from 'react-router-dom'

const steps = [
  {
    number: '01',
    title: '上传音乐',
    desc: '支持 MP3、WAV、M4A、FLAC 格式，拖拽即可上传',
    icon: '🎵',
    color: 'from-purple-500 to-indigo-500',
  },
  {
    number: '02',
    title: '选择高潮区间',
    desc: '可视化波形展示，精准选取最精彩片段',
    icon: '🎶',
    color: 'from-indigo-500 to-blue-500',
  },
  {
    number: '03',
    title: '选择形象与模型',
    desc: '预设数字人形象 + 三款 AI 模型自由搭配',
    icon: '🧑‍🎤',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    number: '04',
    title: '生成视频',
    desc: '一键生成，实时查看进度，下载高清视频',
    icon: '🎬',
    color: 'from-cyan-500 to-teal-500',
  },
]

export default function HomePage() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-16">
        <h1 className="text-5xl sm:text-6xl font-extrabold mb-4">
          <span className="bg-gradient-to-r from-purple-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
            会唱歌的数字人
          </span>
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto">
          上传音乐，选择形象，AI 自动生成数字人演唱视频
        </p>
        <Link
          to="/create"
          className="inline-flex items-center gap-2 mt-8 px-8 py-3.5 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold text-lg shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-105 transition-all duration-300"
        >
          开始创作
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {steps.map((step) => (
          <div
            key={step.number}
            className="group relative bg-[#1a1d2e] rounded-2xl p-6 border border-white/5 hover:border-white/10 transition-all duration-300 hover:-translate-y-1 hover:shadow-xl hover:shadow-purple-500/5"
          >
            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${step.color} flex items-center justify-center text-2xl mb-4 shadow-lg`}>
              {step.icon}
            </div>
            <div className="text-xs font-bold text-gray-500 mb-1">STEP {step.number}</div>
            <h3 className="text-lg font-bold text-gray-100 mb-2">{step.title}</h3>
            <p className="text-sm text-gray-400 leading-relaxed">{step.desc}</p>
          </div>
        ))}
      </div>

      <div className="mt-20 text-center">
        <div className="inline-flex items-center gap-6 px-8 py-4 rounded-2xl bg-[#1a1d2e] border border-white/5">
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-400">3</div>
            <div className="text-xs text-gray-500">AI 模型</div>
          </div>
          <div className="w-px h-8 bg-white/10" />
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-400">4</div>
            <div className="text-xs text-gray-500">音频格式</div>
          </div>
          <div className="w-px h-8 bg-white/10" />
          <div className="text-center">
            <div className="text-2xl font-bold text-cyan-400">∞</div>
            <div className="text-xs text-gray-500">创意可能</div>
          </div>
        </div>
      </div>
    </div>
  )
}
