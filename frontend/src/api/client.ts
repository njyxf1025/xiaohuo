const BASE_URL = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: res.statusText }))
    throw new Error(error.message || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function uploadMusic(file: File, onProgress?: (percent: number) => void): Promise<{ fileId: string; filename: string; duration: number }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE_URL}/music/upload`)
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100))
      }
    })
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText))
        } catch {
          reject(new Error('Invalid response'))
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`))
      }
    })
    xhr.addEventListener('error', () => reject(new Error('Network error')))
    const formData = new FormData()
    formData.append('file', file)
    xhr.send(formData)
  })
}

export async function getWaveform(fileId: string): Promise<{ data: number[]; duration: number }> {
  return request(`/music/waveform/${fileId}`)
}

export async function getAvatarList(): Promise<{ id: string; name: string; thumbnail: string }[]> {
  return request('/avatar/list')
}

export async function uploadAvatar(file: File): Promise<{ id: string; name: string; thumbnail: string }> {
  const formData = new FormData()
  formData.append('file', file)
  return request('/avatar/upload', {
    method: 'POST',
    body: formData,
  })
}

export async function generateVideo(params: {
  musicFileId: string;
  avatarId: string;
  model: string;
  startTime: number;
  endTime: number;
}): Promise<{ taskId: string }> {
  return request('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export async function getGenerationStatus(taskId: string): Promise<{
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  step: string;
  videoUrl?: string;
}> {
  return request(`/generate/${taskId}/status`)
}

export async function getHistory(): Promise<{
  id: string;
  musicName: string;
  avatarName: string;
  model: string;
  videoUrl: string;
  createdAt: string;
}[]> {
  return request('/history')
}
