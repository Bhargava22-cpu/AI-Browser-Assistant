import { useState, useEffect } from 'react'

const EMPTY = {
  name: '', email: '', phone: '',
  address: { street: '', city: '', state: '', pincode: '', country: '' },
  college: '', degree: '', graduation_year: '',
  skills: '', resume_path: '', linkedin: '', github: '',
}

function Field({ label, name, value, onChange, type = 'text' }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-gray-400">{label}</label>
      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-indigo-500"
      />
    </div>
  )
}

export default function ProfileSettings() {
  const [form, setForm] = useState(EMPTY)
  const [status, setStatus] = useState(null) // 'saving' | 'saved' | 'error'

  useEffect(() => {
    fetch('/user/profile')
      .then(r => r.json())
      .then(data => {
        setForm({
          ...data,
          skills: Array.isArray(data.skills) ? data.skills.join(', ') : data.skills,
          address: typeof data.address === 'object' ? data.address : EMPTY.address,
        })
      })
      .catch(err => console.error('Failed to load profile:', err))
  }, [])

  function handleChange(e) {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, [name]: value }))
  }

  function handleAddressChange(e) {
    const { name, value } = e.target
    setForm(prev => ({ ...prev, address: { ...prev.address, [name]: value } }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('saving')
    try {
      const payload = {
        ...form,
        graduation_year: Number(form.graduation_year),
        skills: form.skills.split(',').map(s => s.trim()).filter(Boolean),
      }
      const res = await fetch('/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error()
      setStatus('saved')
      setTimeout(() => setStatus(null), 3000)
    } catch {
      setStatus('error')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-6">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">User Profile</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Name"  name="name"  value={form.name}  onChange={handleChange} />
        <Field label="Email" name="email" value={form.email} onChange={handleChange} type="email" />
        <Field label="Phone" name="phone" value={form.phone} onChange={handleChange} />
      </div>

      <fieldset className="border border-gray-800 rounded-xl p-4 flex flex-col gap-4">
        <legend className="text-xs text-gray-500 px-1">Address</legend>
        <Field label="Street"  name="street"  value={form.address.street}  onChange={handleAddressChange} />
        <div className="grid grid-cols-2 gap-4">
          <Field label="City"    name="city"    value={form.address.city}    onChange={handleAddressChange} />
          <Field label="State"   name="state"   value={form.address.state}   onChange={handleAddressChange} />
          <Field label="Pincode" name="pincode" value={form.address.pincode} onChange={handleAddressChange} />
          <Field label="Country" name="country" value={form.address.country} onChange={handleAddressChange} />
        </div>
      </fieldset>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="College"         name="college"         value={form.college}         onChange={handleChange} />
        <Field label="Degree"          name="degree"          value={form.degree}          onChange={handleChange} />
        <Field label="Graduation Year" name="graduation_year" value={form.graduation_year} onChange={handleChange} type="number" />
        <Field label="Skills (comma-separated)" name="skills" value={form.skills} onChange={handleChange} />
        <Field label="Resume Path" name="resume_path" value={form.resume_path} onChange={handleChange} />
        <Field label="LinkedIn"    name="linkedin"    value={form.linkedin}    onChange={handleChange} />
        <Field label="GitHub"      name="github"      value={form.github}      onChange={handleChange} />
      </div>

      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={status === 'saving'}
          className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {status === 'saving' ? 'Saving…' : 'Save Profile'}
        </button>
        {status === 'saved' && <span className="text-emerald-400 text-sm">Saved successfully</span>}
        {status === 'error' && <span className="text-red-400 text-sm">Save failed — check the server</span>}
      </div>
    </form>
  )
}
