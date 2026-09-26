import { useState, useRef, useEffect } from 'react'

export function Registration() {
  const [rollNo, setRollNo] = useState('')
  const [name, setName] = useState('')
  const [classDiv, setClassDiv] = useState('A')
  
  const [status, setStatus] = useState({ type: '', msg: '' })
  const videoRef = useRef<HTMLVideoElement>(null)
  
  useEffect(() => {
    // Start webcam
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(stream => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      })
      .catch(err => setStatus({ type: 'error', msg: 'Webcam access denied: ' + err.message }))
      
    return () => {
      // Stop webcam on unmount
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream
        stream.getTracks().forEach(t => t.stop())
      }
    }
  }, [])

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault()
    if (!rollNo || !name) return
    setStatus({ type: 'info', msg: 'Capturing photo & registering...' })

    try {
      // 1. Create student record
      const sRes = await fetch('/api/students', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roll_no: parseInt(rollNo), name, class_div: classDiv })
      })
      if (!sRes.ok) throw new Error('Failed to create student record. Roll number might already exist.')

      // 2. Capture frame from video
      const video = videoRef.current
      if (!video) throw new Error('No webcam video')
      
      const canvas = document.createElement('canvas')
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      const ctx = canvas.getContext('2d')
      ctx?.drawImage(video, 0, 0)
      const base64Image = canvas.toDataURL('image/jpeg')

      // 3. Send face registration
      const fRes = await fetch(`/api/students/${rollNo}/face`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_base64: base64Image })
      })
      
      const data = await fRes.json()
      if (!fRes.ok) throw new Error(data.detail || 'Failed to extract face embedding')

      setStatus({ type: 'success', msg: `Successfully registered ${name} (Roll ${rollNo})!` })
      setRollNo('')
      setName('')
    } catch (err: any) {
      setStatus({ type: 'error', msg: err.message })
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 20 }}>Student Registration</h2>
      
      <div style={{ display: 'flex', gap: 40 }}>
        {/* Left: Form */}
        <div style={{ flex: 1, background: 'var(--surface)', padding: 24, borderRadius: 12 }}>
          <h3 style={{ marginBottom: 16 }}>1. Enter Details</h3>
          <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              Roll Number
              <input type="number" required value={rollNo} onChange={e=>setRollNo(e.target.value)} 
                style={{ padding: 8, background: 'var(--bg)', color: 'white', border: '1px solid var(--border)', borderRadius: 6 }}/>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              Full Name
              <input type="text" required value={name} onChange={e=>setName(e.target.value)}
                style={{ padding: 8, background: 'var(--bg)', color: 'white', border: '1px solid var(--border)', borderRadius: 6 }}/>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              Class/Division
              <input type="text" required value={classDiv} onChange={e=>setClassDiv(e.target.value)}
                style={{ padding: 8, background: 'var(--bg)', color: 'white', border: '1px solid var(--border)', borderRadius: 6 }}/>
            </label>
            
            <button type="submit" className="btn btn-primary" style={{ padding: 12, marginTop: 16 }}>
              Capture Face & Register
            </button>
          </form>
          
          {status.msg && (
            <div style={{ marginTop: 20, padding: 12, borderRadius: 6, 
              background: status.type === 'error' ? 'var(--red)' : status.type === 'success' ? 'var(--green)' : 'var(--accent)',
              color: status.type === 'error' ? 'white' : 'black'
            }}>
              {status.msg}
            </div>
          )}
        </div>
        
        {/* Right: Camera */}
        <div style={{ flex: 1, background: 'var(--surface)', padding: 24, borderRadius: 12 }}>
          <h3 style={{ marginBottom: 16 }}>2. Face Capture</h3>
          <p style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 12 }}>
            Ensure the student is looking directly at the camera with good lighting. Only ONE face should be visible.
          </p>
          <div style={{ background: '#000', borderRadius: 8, overflow: 'hidden', aspectRatio: '4/3', position: 'relative' }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </div>
        </div>
      </div>
    </div>
  )
}
