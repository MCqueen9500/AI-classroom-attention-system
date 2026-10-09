// src/pages/Registration.tsx
import { useState, useRef, useEffect } from 'react'

export function Registration() {
  const [rollNo, setRollNo] = useState('')
  const [name, setName] = useState('')
  const [classDiv, setClassDiv] = useState('A')
  
  const [status, setStatus] = useState({ type: '', msg: '' })
  const videoRef = useRef<HTMLVideoElement>(null)
  
  useEffect(() => {
    navigator.mediaDevices.getUserMedia({ video: true })
      .then(stream => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      })
      .catch(err => setStatus({ type: 'error', msg: 'Webcam access denied: ' + err.message }))
      
    return () => {
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

    const token = localStorage.getItem('token')
    const authHeader: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}

    try {
      // 1. Create student record
      const sRes = await fetch('/api/students', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ roll_no: parseInt(rollNo), name, class_div: classDiv })
      })
      if (!sRes.ok && sRes.status !== 400) {
          throw new Error('Failed to create student record. Roll number might already exist.')
      }

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
        headers: { 'Content-Type': 'application/json', ...authHeader },
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
    <div className="max-w-[1000px] mx-auto py-8">
      <div className="mb-10 border-b border-blue/20 pb-4">
        <h2 className="text-3xl font-black uppercase tracking-tight text-blue">Student Registration</h2>
        <p className="text-blue/60 text-sm mt-2 font-medium tracking-wide">Enroll faces to the edge recognition system</p>
      </div>
      
      <div className="grid md:grid-cols-2 gap-8">
        
        {/* Left: Form */}
        <div className="bg-ivory border border-blue/20 p-8 shadow-sm">
          <div className="flex items-center gap-4 mb-8">
             <div className="w-8 h-8 rounded-full border-2 border-blue flex items-center justify-center font-black text-blue">1</div>
             <h3 className="text-sm uppercase tracking-widest font-bold text-blue">Enter Details</h3>
          </div>
          
          <form onSubmit={handleRegister} className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <label className="text-[10px] uppercase tracking-widest font-bold text-blue/60">Roll Number</label>
              <input type="number" required value={rollNo} onChange={e=>setRollNo(e.target.value)} 
                className="bg-transparent border-b-2 border-blue/20 px-0 py-2 text-blue font-bold outline-none focus:border-coral transition-colors" placeholder="e.g. 14"/>
            </div>
            
            <div className="flex flex-col gap-2">
              <label className="text-[10px] uppercase tracking-widest font-bold text-blue/60">Full Name</label>
              <input type="text" required value={name} onChange={e=>setName(e.target.value)}
                className="bg-transparent border-b-2 border-blue/20 px-0 py-2 text-blue font-bold outline-none focus:border-coral transition-colors" placeholder="e.g. Jane Doe"/>
            </div>
            
            <div className="flex flex-col gap-2">
              <label className="text-[10px] uppercase tracking-widest font-bold text-blue/60">Class / Division</label>
              <input type="text" required value={classDiv} onChange={e=>setClassDiv(e.target.value)}
                className="bg-transparent border-b-2 border-blue/20 px-0 py-2 text-blue font-bold outline-none focus:border-coral transition-colors" placeholder="e.g. A"/>
            </div>
            
            <button type="submit" className="mt-8 bg-blue text-ivory text-xs uppercase tracking-[0.2em] font-bold py-4 hover:bg-coral transition-colors">
              Capture & Enroll
            </button>
          </form>
          
          {status.msg && (
            <div className={`mt-6 p-4 border text-xs font-bold uppercase tracking-widest ${
              status.type === 'error' ? 'bg-coral/10 border-coral text-coral' : 
              status.type === 'success' ? 'bg-green-100 border-green-600 text-green-700' : 
              'bg-blue/5 border-blue text-blue'
            }`}>
              {status.msg}
            </div>
          )}
        </div>
        
        {/* Right: Camera */}
        <div className="bg-ivory border border-blue/20 p-8 shadow-sm">
          <div className="flex items-center gap-4 mb-4">
             <div className="w-8 h-8 rounded-full border-2 border-blue flex items-center justify-center font-black text-blue">2</div>
             <h3 className="text-sm uppercase tracking-widest font-bold text-blue">Face Capture</h3>
          </div>
          
          <p className="text-xs text-blue/50 font-medium mb-6 leading-relaxed">
            Ensure the student is looking directly at the camera in good lighting. Only ONE face should be visible.
          </p>
          
          <div className="bg-blue/5 border-2 border-dashed border-blue/20 rounded-sm overflow-hidden aspect-[4/3] relative p-1">
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover rounded-sm grayscale-[20%] contrast-125" />
            
            {/* Viewfinder Overlay */}
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
              <div className="w-1/3 h-1/2 border-2 border-coral/50 border-dashed rounded-[100px] opacity-70"></div>
            </div>
          </div>
        </div>
        
      </div>
    </div>
  )
}
