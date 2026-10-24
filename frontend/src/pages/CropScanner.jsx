import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { useFarm } from '../context/FarmContext'
import toast from 'react-hot-toast'
import {
  AlertTriangle, ArrowRight, CheckCircle2, ImagePlus, Info, Leaf,
  LoaderCircle, ScanLine, ShieldAlert, Target, Upload, X
} from 'lucide-react'

function confidenceLabel(value) {
  if (value >= 80) return 'Higher estimate'
  if (value >= 55) return 'Moderate estimate'
  return 'Low estimate'
}

function confidenceColor(value) {
  if (value >= 80) return 'text-emerald-700 bg-emerald-50'
  if (value >= 55) return 'text-amber-700 bg-amber-50'
  return 'text-red-700 bg-red-50'
}

function formatDiseaseName(value) {
  return value?.replace(/_/g, ' ') || 'Assessment unavailable'
}

export default function CropScanner() {
  const { activeFarm } = useFarm()
  const fields = activeFarm?.fields || []
  const [image, setImage] = useState(null)
  const [preview, setPreview] = useState('')
  const [selectedFieldId, setSelectedFieldId] = useState('')
  const [scanning, setScanning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [modelStatus, setModelStatus] = useState(null)
  const [modelStatusError, setModelStatusError] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef(null)

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview)
  }, [preview])

  useEffect(() => {
    api.get('/scans/model-status')
      .then((response) => {
        setModelStatus(response.data)
        setModelStatusError('')
      })
      .catch((requestError) => {
        setModelStatusError(
          requestError.response?.data?.detail || 'Could not check model status.'
        )
      })
  }, [])

  const handleFile = (file) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('Choose a JPG, PNG, or WebP image.')
      toast.error('Upload a JPG, PNG, or WebP image')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('This image is larger than 10 MB. Choose a smaller image.')
      toast.error('Image must be 10 MB or smaller')
      return
    }
    setImage(file)
    setResult(null)
    setError('')
    setPreview(URL.createObjectURL(file))
  }

  const handleDrop = useCallback((event) => {
    event.preventDefault()
    setDragOver(false)
    handleFile(event.dataTransfer.files[0])
  }, [])

  const clearImage = () => {
    setImage(null)
    setPreview('')
    setResult(null)
    setError('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleScan = async (event) => {
    event.preventDefault()
    if (!image) {
      setError('Upload a clear crop or leaf photo before starting the scan.')
      return
    }
    const targetFieldId = selectedFieldId || fields[0]?.id
    if (!targetFieldId) {
      setError('Add a farm field before scanning so this result can be saved to the right field.')
      return
    }

    setScanning(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('file', image)
      formData.append('field_id', targetFieldId)
      const response = await api.post('/scans', formData, { timeout: 90_000 })
      setResult(response.data)
      toast.success('Crop image assessed and saved')
    } catch (requestError) {
      const message = requestError.response?.data?.detail
        || (requestError.code === 'ECONNABORTED'
          ? 'Crop analysis timed out. Try again with a smaller image.'
          : 'Crop scan failed. Check your connection and try again.')
      setError(message)
      toast.error(message)
    } finally {
      setScanning(false)
    }
  }

  const resultField = fields.find((field) => String(field.id) === String(result?.field_id))
  const confidence = Number(result?.confidence ?? 0)
  const detectorName = result?.detector_source?.startsWith('groq:')
    ? `Groq · ${result.detector_source.slice(5)}`
    : result?.detector_source || 'AI model'

  return (
    <div className="mx-auto max-w-6xl space-y-6 pb-8">
      <header className="rounded-2xl border border-emerald-100 bg-gradient-to-br from-white to-emerald-50 p-5 shadow-sm sm:p-7">
        <p className="eyebrow">Image assessment</p>
        <h1 className="section-title">Crop scanner</h1>
        <p className="section-subtitle max-w-3xl">
          Upload a clear crop photo to get an AI visual assessment. When the trained local model is unavailable, the image is analyzed using your configured Groq vision service.
        </p>
        <div className="mt-4 flex items-start gap-2 rounded-xl border border-sky-100 bg-sky-50 p-3 text-xs leading-5 text-sky-900">
          <Info size={16} className="mt-0.5 shrink-0" />
          <p>
            Per-image confidence is only an AI estimate and is different from the held-out test accuracy shown below. This is not a confirmed diagnosis; severity still needs a field assessment.
          </p>
        </div>
        <div className="mt-3 rounded-xl border border-gray-200 bg-white p-3 text-xs text-gray-700" role="status">
          {modelStatusError ? (
            <span className="text-amber-800">{modelStatusError}</span>
          ) : !modelStatus ? (
            <span>Checking crop model status…</span>
          ) : !modelStatus.available ? (
            <span className="text-amber-800">No crop model is ready. Configure Groq or install the trained local checkpoint.</span>
          ) : modelStatus.provider === 'local' ? (
            <div className="space-y-1">
              <p>
                Local model: <strong>{modelStatus.model}</strong>
                {modelStatus.held_out_test_accuracy == null
                  ? ' · Held-out test accuracy has not been evaluated.'
                  : ` · Held-out dataset test accuracy: ${(modelStatus.held_out_test_accuracy * 100).toFixed(1)}% across ${modelStatus.held_out_test_samples} test images.`}
              </p>
              <p>
                Trained classes: {(modelStatus.classes || []).map((name) => name.replace(/_+/g, ' ')).join(', ')}.
                {modelStatus.groq_available ? ` Other crops use Groq vision (${modelStatus.groq_model}).` : ' Other crop types are not supported by this local model.'}
              </p>
            </div>
          ) : (
            <span>
              Vision provider: <strong>{modelStatus.model}</strong> · No held-out accuracy report is available for this AI service.
            </span>
          )}
        </div>
      </header>

      <div className="grid items-stretch gap-5 lg:grid-cols-2">
        <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <form onSubmit={handleScan} className="space-y-5">
            <div>
              <label htmlFor="scan-field" className="mb-2 block text-sm font-semibold text-gray-800">
                Select the farm field
              </label>
              {fields.length ? (
                <select
                  id="scan-field"
                  value={selectedFieldId || fields[0].id}
                  onChange={(event) => setSelectedFieldId(event.target.value)}
                  className="farm-input w-full"
                  disabled={scanning}
                >
                  {fields.map((field) => (
                    <option key={field.id} value={field.id}>
                      {field.name} · {field.crop_type || field.crop || 'Crop not specified'}
                      {field.growth_stage ? ` · ${field.growth_stage}` : ''}
                      {field.size_acres ? ` · ${field.size_acres} acres` : ''}
                    </option>
                  ))}
                </select>
              ) : (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  <p className="font-semibold">No field available in this farm</p>
                  <p className="mt-1 text-xs">Create a farm and field before saving a scan.</p>
                  <Link to="/farms" className="mt-3 inline-flex items-center gap-1 font-semibold underline">
                    Open My Farms <ArrowRight size={14} />
                  </Link>
                </div>
              )}
            </div>

            <div>
              <p className="mb-2 text-sm font-semibold text-gray-800">Upload a crop photo</p>
              <div
                onDrop={handleDrop}
                onDragOver={(event) => { event.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                className={`relative flex min-h-72 flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed p-5 text-center transition ${
                  dragOver ? 'border-emerald-500 bg-emerald-50' : 'border-emerald-200 bg-emerald-50/40 hover:bg-emerald-50'
                }`}
              >
                {preview ? (
                  <>
                    <img src={preview} alt="Selected crop leaf preview" className="max-h-64 max-w-full rounded-xl object-contain shadow-sm" />
                    <p className="mt-3 max-w-full truncate text-sm font-medium text-gray-700">{image?.name}</p>
                    <button
                      type="button"
                      onClick={clearImage}
                      disabled={scanning}
                      className="absolute right-3 top-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-white text-gray-600 shadow hover:text-red-600"
                      aria-label="Remove selected image"
                    >
                      <X size={17} />
                    </button>
                  </>
                ) : (
                  <>
                    <span className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                      <ImagePlus size={27} />
                    </span>
                    <p className="font-semibold text-gray-800">Drop a crop photo here</p>
                    <p className="mt-1 text-sm text-gray-500">or browse JPG, PNG, WebP · up to 10 MB</p>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="btn-secondary mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm"
                    >
                      <Upload size={15} /> Choose image
                    </button>
                  </>
                )}
              </div>
              <input
                ref={fileInputRef}
                id="crop-image"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={(event) => handleFile(event.target.files[0])}
                aria-label="Choose crop image"
              />
            </div>

            {error && (
              <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
                <AlertTriangle size={17} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={!image || !fields.length || scanning}
              className="btn-primary inline-flex min-h-12 w-full items-center justify-center gap-2 px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
            >
              {scanning
                ? <><LoaderCircle size={18} className="animate-spin" /> Analyzing image…</>
                : <><ScanLine size={17} /> Analyze and save scan</>}
            </button>
            <p className="text-center text-xs text-gray-500">
              The selected photo is sent to the configured AI provider for analysis and saved with this field.
            </p>
          </form>
        </section>

        <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6" aria-live="polite">
          {result ? (
            <div className="space-y-5">
              <div className="flex items-start gap-3 border-b border-gray-100 pb-4">
                <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                  <Leaf size={22} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="eyebrow">AI visual assessment</p>
                  <h2 className="text-xl font-bold text-gray-900">{formatDiseaseName(result.disease_name)}</h2>
                  <p className="mt-1 text-sm text-gray-500">
                    {resultField?.name || `Field ${result.field_id}`} · {resultField?.crop_type || resultField?.crop || 'Crop not specified'}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold capitalize text-gray-700">
                  {result.severity === 'unassessed' ? 'Severity not assessed' : result.severity}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className={`rounded-xl p-4 ${confidenceColor(confidence)}`}>
                  <p className="text-xs font-semibold">AI confidence estimate</p>
                  <p className="mt-1 text-2xl font-bold">{confidence.toFixed(1)}%</p>
                  <p className="mt-1 text-xs">{confidenceLabel(confidence)} · not validated accuracy</p>
                </div>
                <div className="rounded-xl bg-gray-50 p-4">
                  <p className="text-xs font-semibold text-gray-500">Analysis model</p>
                  <p className="mt-2 break-words text-sm font-semibold text-gray-900">{detectorName}</p>
                  <p className="mt-1 text-xs text-gray-500">Saved {result.created_at ? new Date(result.created_at).toLocaleString() : 'just now'}</p>
                </div>
              </div>

              {result.alternatives?.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-gray-800">Other possible matches</h3>
                  <ul className="space-y-2">
                    {result.alternatives.map((alternative, index) => (
                      <li key={`${alternative.class_name}-${index}`} className="flex items-center justify-between gap-3 rounded-lg border border-gray-100 px-3 py-2 text-sm">
                        <span className="text-gray-700">{alternative.class_name}</span>
                        <span className="shrink-0 text-xs font-semibold text-gray-500">{alternative.confidence}% estimate</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                <ShieldAlert size={16} className="mt-0.5 shrink-0" />
                <p>AI image results can be wrong. This is not a confirmed diagnosis. Check the crop in person or consult an agricultural expert before treatment.</p>
              </div>

              <div className="grid gap-2">
                <Link to={`/rescue/${result.id}`} className="btn-secondary inline-flex items-center justify-center gap-2 px-3 py-2.5 text-sm">
                  <Target size={16} /> Verify diagnosis and view rescue plan
                </Link>
                <p className="text-center text-xs text-gray-500">
                  The diagnosis step sends this saved crop photo to your configured Groq vision model for review.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[440px] flex-col items-center justify-center px-4 text-center">
              <span className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
                <ScanLine size={31} />
              </span>
              <h2 className="mt-5 text-lg font-bold text-gray-900">{scanning ? 'Analyzing your crop photo' : 'Your assessment will appear here'}</h2>
              <p className="mt-2 max-w-sm text-sm leading-6 text-gray-500">
                {scanning
                  ? 'The image is being checked by the configured vision model. This can take a little while.'
                  : 'Choose a farm field and upload a clear leaf or crop image to start an assessment.'}
              </p>
              <ul className="mt-6 space-y-3 text-left text-sm text-gray-600">
                {[
                  'Returns a likely visible crop condition',
                  'Shows alternative AI matches when available',
                  'Keeps image confidence separate from field severity',
                ].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="shrink-0 text-emerald-600" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
