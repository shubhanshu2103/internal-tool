import { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, CheckCircle, XCircle, Loader2, Database, FileSearch, Check, FileCheck2 } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

function App() {
  // EVALUATE (Left Panel) State
  const [evalFile, setEvalFile] = useState(null);
  const [evalToolName, setEvalToolName] = useState('');
  const [evalToolCategory, setEvalToolCategory] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);
  
  // INGEST (Right Panel) State
  const [ingestFile, setIngestFile] = useState(null);
  const [ingestToolName, setIngestToolName] = useState('');
  const [ingestToolCategory, setIngestToolCategory] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState('');

  // CENTER FEEDBACK State
  const [feedback, setFeedback] = useState(null);
  const [centerStatus, setCenterStatus] = useState(''); // E.g., 'Declined', 'Approved'

  const handleEvaluate = async (e) => {
    e.preventDefault();
    if (!evalFile) return alert("Please select a file to evaluate.");
    
    setIsEvaluating(true);
    setFeedback(null);
    setCenterStatus('');
    
    const formData = new FormData();
    formData.append('file', evalFile);
    formData.append('tool_name', evalToolName || 'Unknown');
    formData.append('tool_category', evalToolCategory || 'Unknown');

    try {
      const res = await axios.post(`${API_BASE}/evaluate/file`, formData);
      setFeedback(res.data.result);
    } catch (err) {
      console.error(err);
      alert("Evaluation failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleIngest = async (e) => {
    e.preventDefault();
    if (!ingestFile) return alert("Please select an approved file to ingest.");
    
    setIsIngesting(true);
    setIngestStatus('');
    
    const formData = new FormData();
    formData.append('file', ingestFile);
    formData.append('tool_name', ingestToolName || 'Unknown');
    formData.append('tool_category', ingestToolCategory || 'Unknown');
    formData.append('review_date', new Date().toISOString().split('T')[0]);

    try {
      await axios.post(`${API_BASE}/ingest/upload`, formData);
      await axios.post(`${API_BASE}/ingest/rubric`);
      setIngestStatus('Successfully ingested and built rubric!');
      
      // clear fields
      setIngestFile(null);
      setIngestToolName('');
      setIngestToolCategory('');
      e.target.reset();
    } catch (err) {
      console.error(err);
      setIngestStatus("Ingestion failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setIsIngesting(false);
    }
  };

  const handleApproveFeedback = async () => {
    // Take the evalFile and ingest it!
    setIsEvaluating(true);
    
    const formData = new FormData();
    formData.append('file', evalFile);
    formData.append('tool_name', feedback.tool_name);
    formData.append('tool_category', feedback.tool_category);
    formData.append('review_date', new Date().toISOString().split('T')[0]);

    try {
      await axios.post(`${API_BASE}/ingest/upload`, formData);
      await axios.post(`${API_BASE}/ingest/rubric`);
      setCenterStatus('APPROVED');
      setFeedback(null);
    } catch (err) {
      console.error(err);
      alert("Action failed: " + err.message);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleDeclineFeedback = () => {
    setCenterStatus('DECLINED');
    setFeedback(null);
  };

  return (
    <div className="dashboard-layout">
      
      {/* LEFT PANEL: UPLOAD DRAFT */}
      <div className="glass-panel">
        <h2><FileSearch size={22} /> Evaluate Draft Review</h2>
        <p style={{marginBottom: '1.5rem', color: 'var(--text-muted)', fontSize: '0.9rem'}}>
          Upload an unapproved review to test it against the strict internal knowledge rubric.
        </p>
        
        <form onSubmit={handleEvaluate} style={{display: 'flex', flexDirection: 'column', flex: 1}}>
          <div className="form-group">
            <label>Tool Name</label>
            <input 
              type="text" 
              placeholder="e.g. Vercel" 
              value={evalToolName}
              onChange={(e) => setEvalToolName(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Tool Category</label>
            <input 
              type="text" 
              placeholder="e.g. CI/CD" 
              value={evalToolCategory}
              onChange={(e) => setEvalToolCategory(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Draft Document (PDF/DOCX/TXT)</label>
            <input 
              type="file" 
              onChange={(e) => setEvalFile(e.target.files[0])}
              required
            />
          </div>
          
          <button type="submit" className="btn" disabled={isEvaluating}>
            {isEvaluating ? <><Loader2 className="lucide-spin" size={18}/> Scoring...</> : 'Run RAG Evaluation'}
          </button>
        </form>
      </div>

      {/* CENTER PANEL: FEEDBACK */}
      <div className="glass-panel" style={{ background: 'rgba(18, 22, 28, 0.4)' }}>
        
        {!feedback && !centerStatus && (
          <div className="empty-state">
            <Database />
            <p>Awaiting Document Evaluation...</p>
          </div>
        )}

        {centerStatus === 'DECLINED' && (
          <div className="empty-state">
            <XCircle color="var(--fail)" size={48} />
            <span style={{ color: 'var(--fail)', fontWeight: '600', fontSize: '1.5rem' }}>The review was declined.</span>
          </div>
        )}

        {centerStatus === 'APPROVED' && (
          <div className="empty-state">
            <CheckCircle color="var(--success)" size={48} />
            <span style={{ color: 'var(--success)', fontWeight: '600', fontSize: '1.5rem' }}>The review was approved and ingested!</span>
          </div>
        )}

        {feedback && (
          <div className="feedback-container">
            <div className="feedback-header">
              <h1>{feedback.overall_score} <span style={{fontSize: '1.5rem', color: 'var(--text-muted)'}}>/ 10</span></h1>
              <span className={`score-badge ${feedback.overall_label}`}>
                {feedback.overall_label}
              </span>
            </div>

            {['relevance', 'depth', 'precision', 'outcomes', 'coverage'].map(dim => {
               const data = feedback[dim];
               if (!data) return null;
               return (
                 <div key={dim} className={`dim-card ${data.label}`}>
                   <div className="dim-header">
                     <h3>{dim}</h3>
                     <span className="dim-score">{data.score}/10</span>
                   </div>
                   <p>{data.rationale}</p>
                   {data.suggestion && (
                     <div className="suggestion-box">
                       <strong>Action Required:</strong> {data.suggestion}
                     </div>
                   )}
                 </div>
               )
            })}

            <div className="action-row">
              <button className="btn btn-secondary btn-danger" onClick={handleDeclineFeedback}>
                <XCircle size={18} /> Decline Review
              </button>
              <button className="btn btn-success" onClick={handleApproveFeedback} disabled={isEvaluating}>
                <FileCheck2 size={18} /> Approve & Ingest
              </button>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT PANEL: DIRECT INGESTION */}
      <div className="glass-panel">
        <h2><Database size={22} /> Ingest Approved Review</h2>
        <p style={{marginBottom: '1.5rem', color: 'var(--text-muted)', fontSize: '0.9rem'}}>
          Directly train the semantic model by uploading a perfectly approved corporate review.
        </p>

        <form onSubmit={handleIngest} style={{display: 'flex', flexDirection: 'column', flex: 1}}>
          <div className="form-group">
            <label>Tool Name</label>
            <input 
              type="text" 
              placeholder="e.g. AWS" 
              value={ingestToolName}
              onChange={(e) => setIngestToolName(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Tool Category</label>
            <input 
              type="text" 
              placeholder="e.g. Cloud" 
              value={ingestToolCategory}
              onChange={(e) => setIngestToolCategory(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Approved Document</label>
            <input 
              type="file" 
              onChange={(e) => setIngestFile(e.target.files[0])}
              required
            />
          </div>

          {ingestStatus && (
            <div style={{ padding: '0.75rem', background: 'rgba(16, 185, 129, 0.1)', color: 'var(--success)', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.85rem' }}>
              <Check size={14} style={{verticalAlign: 'middle', marginRight: '4px'}}/>
              {ingestStatus}
            </div>
          )}

          <button type="submit" className="btn btn-secondary" disabled={isIngesting}>
            {isIngesting ? <><Loader2 className="lucide-spin" size={18}/> Ingesting...</> : 'Upload & Train'}
          </button>
        </form>
      </div>

    </div>
  );
}

export default App;
