interface ModelSelectorProps {
  selected: string
  onSelect: (model: string) => void
}

const models = [
  {
    id: 'wav2lip',
    name: 'Wav2Lip',
    desc: '基于唇形同步的经典模型，生成速度快，适合快速预览和批量生成',
    speed: 5,
    quality: 3,
    badge: '速度快',
    badgeColor: 'bg-green-500/10 text-green-400',
  },
  {
    id: 'sadtalker',
    name: 'SadTalker',
    desc: '单张图片驱动的说话人模型，兼顾表情自然度与生成效率',
    speed: 3,
    quality: 4,
    badge: '平衡',
    badgeColor: 'bg-blue-500/10 text-blue-400',
  },
  {
    id: 'latentsync',
    name: 'LatentSync',
    desc: '基于潜空间的高精度唇形同步模型，生成质量最高，适合最终输出',
    speed: 1,
    quality: 5,
    badge: '质量高',
    badgeColor: 'bg-purple-500/10 text-purple-400',
  },
]

export default function ModelSelector({ selected, onSelect }: ModelSelectorProps) {
  return (
    <div>
      <h2 className="text-xl font-bold text-gray-100 mb-4">选择生成模型</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {models.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => onSelect(m.id)}
            className={`text-left rounded-2xl p-5 border-2 transition-all duration-300 hover:-translate-y-0.5 ${
              selected === m.id
                ? 'border-purple-500 bg-purple-500/5 shadow-lg shadow-purple-500/10'
                : 'border-white/5 bg-[#1a1d2e] hover:border-white/15'
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-gray-100">{m.name}</h3>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${m.badgeColor}`}>
                {m.badge}
              </span>
            </div>
            <p className="text-sm text-gray-400 leading-relaxed mb-4">{m.desc}</p>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-8">速度</span>
                <div className="flex gap-0.5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      className={`w-4 h-1.5 rounded-full ${
                        i < m.speed ? 'bg-green-400' : 'bg-white/10'
                      }`}
                    />
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-8">质量</span>
                <div className="flex gap-0.5">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <div
                      key={i}
                      className={`w-4 h-1.5 rounded-full ${
                        i < m.quality ? 'bg-purple-400' : 'bg-white/10'
                      }`}
                    />
                  ))}
                </div>
              </div>
            </div>
            {selected === m.id && (
              <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-1.5">
                <div className="w-4 h-4 rounded-full bg-purple-500 flex items-center justify-center">
                  <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="text-xs text-purple-400 font-medium">已选择</span>
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
