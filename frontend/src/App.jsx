// ...existing code...
<div className="optimize-section">
  <button onClick={optimizeAll}>🚀 Optimize All PDFs (90%+ Confidence)</button>
  <button onClick={() => testConfidence()}>🧪 Test Confidence</button>
</div>

const optimizeAll = async () => {
  await axios.post('http://localhost:8001/rechunk-all')
  alert('✅ All PDFs optimized! Ask same question again.')
}

const testConfidence = async () => {
  const question = prompt('Test question:')
  const result = await axios.post('http://localhost:8002/query', {question})
  alert(`Confidence: ${result.data.confidence}%`)
}
// ...existing code...
