import { useState, useEffect } from 'react';
import axios from 'axios';
import { CheckCircle, XCircle, Loader2, Database, FileSearch, Check, FileCheck2, AlertTriangle, Zap, RefreshCw, BookOpen, Layers, Trash2, Link2, Copy, ClipboardCheck } from 'lucide-react';

const DIM_LABELS = {
  relevance: 'Relevance',
  depth: 'Depth',
  precision: 'Precision',
  outcomes: 'Outcomes',
  coverage: 'Coverage',
};

const DIM_DESC = {
  relevance: 'Is the review focused on the right aspects of the tool?',
  depth: 'Is the analysis thorough, detailed, and well-supported?',
  precision: 'Are claims specific, accurate, and evidence-backed?',
  outcomes: 'Are business and technical outcomes clearly articulated?',
  coverage: 'Are all key aspects and use cases of the tool addressed?',
};

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
  const [copied, setCopied] = useState(false);

  // CORPUS State
  const [corpus, setCorpus] = useState(null);
  const [showCorpus, setShowCorpus] = useState(false);

  const fetchCorpus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/ingest/status`);
      setCorpus(res.data);
    } catch (err) {
      console.error('Failed to fetch corpus:', err);
    }
  };

  // HISTORY State
  const [history, setHistory] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API_BASE}/history`);
      setHistory(res.data);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  useEffect(() => { fetchCorpus(); fetchHistory(); }, []);

  const handleDeleteTool = async (toolName) => {
    if (!window.confirm(`Remove "${toolName}" from the corpus? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API_BASE}/ingest/${encodeURIComponent(toolName)}`);
      fetchCorpus();
      setShowCorpus(true);
    } catch (err) {
      alert('Delete failed: ' + (err.response?.data?.detail || err.message));
    }
  };

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
      fetchCorpus();
      setShowCorpus(true);

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
    setIsEvaluating(true);
    const formData = new FormData();
    formData.append('file', evalFile);
    formData.append('tool_name', feedback.tool_name);
    formData.append('tool_category', feedback.tool_category);
    formData.append('review_date', new Date().toISOString().split('T')[0]);
    formData.append('force', 'true');

    try {
      await axios.post(`${API_BASE}/ingest/upload`, formData);
      await axios.post(`${API_BASE}/ingest/rubric`);
      await axios.patch(`${API_BASE}/history/${feedback.review_id}`, { disposition: 'APPROVED' });
      setCenterStatus('APPROVED');
      setFeedback(null);
      fetchCorpus();
      fetchHistory();
      setShowCorpus(true);
      setShowHistory(true);
    } catch (err) {
      console.error(err);
      alert("Action failed: " + err.message);
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleDeclineFeedback = async () => {
    try {
      await axios.patch(`${API_BASE}/history/${feedback.review_id}`, { disposition: 'DECLINED' });
    } catch (err) {
      console.error(err);
    }
    setCenterStatus('DECLINED');
    setFeedback(null);
    fetchHistory();
  };

  const buildShareableText = (fb) => {
    const dims = ['relevance', 'depth', 'precision', 'outcomes', 'coverage'];
    const labelIcon = { PASS: '✓', NOTE: '⚠', FAIL: '✗' };
    const date = new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });

    const dimLines = dims.map(d => {
      const dim = fb[d];
      if (!dim) return '';
      return `  ${labelIcon[dim.label] || '·'} ${DIM_LABELS[d].padEnd(12)} ${dim.score}/10 — ${dim.label}`;
    }).join('\n');

    const analysisSections = dims.map(d => {
      const dim = fb[d];
      if (!dim) return '';
      let block = `${DIM_LABELS[d].toUpperCase()}\n  ${dim.rationale}`;
      if (dim.suggestion) block += `\n  → ${dim.suggestion}`;
      return block;
    }).join('\n\n');

    const suggestions = (fb.top_suggestions || []).map((s, i) => `  ${i + 1}. ${s}`).join('\n');

    return [
      `REVIEW AI — EVALUATION REPORT`,
      `${'═'.repeat(50)}`,
      `Tool     : ${fb.tool_name}`,
      `Category : ${fb.tool_category}`,
      `Date     : ${date}`,
      `Mode     : ${fb.retrieval_mode === 'rag_grounded' ? 'RAG Grounded' : 'Rubric Only'}`,
      ``,
      `OVERALL SCORE : ${Number(fb.overall_score).toFixed(1)}/10 — ${fb.overall_label}`,
      `APPROVAL LIKELIHOOD : ${fb.approval_likelihood}%`,
      ``,
      `${'─'.repeat(50)}`,
      `DIMENSION BREAKDOWN`,
      `${'─'.repeat(50)}`,
      dimLines,
      ``,
      `${'─'.repeat(50)}`,
      `DETAILED ANALYSIS`,
      `${'─'.repeat(50)}`,
      analysisSections,
      ...(suggestions ? [``, `${'─'.repeat(50)}`, `TOP RECOMMENDATIONS`, `${'─'.repeat(50)}`, suggestions] : []),
      ``,
      `${'─'.repeat(50)}`,
      `Generated by Review AI · CoreLayer Labs`,
    ].join('\n');
  };

  const handleCopy = () => {
    if (!feedback) return;
    navigator.clipboard.writeText(buildShareableText(feedback)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
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

            {/* ── Header: tool info + overall score + likelihood ── */}
            <div className="feedback-header">
              <div className="feedback-meta">
                <span className="tool-chip">{feedback.tool_name}</span>
                <span className="category-chip">{feedback.tool_category}</span>
                <span className={`retrieval-chip ${feedback.retrieval_mode}`}>
                  {feedback.retrieval_mode === 'rag_grounded' ? 'RAG Grounded' : 'Rubric Only'}
                </span>
              </div>

              <div className="score-likelihood-row">
                {/* Overall score */}
                <div className="overall-score-block">
                  <div className="overall-score-row">
                    <div className="overall-score-number">
                      <span className="score-big">{Number(feedback.overall_score).toFixed(1)}</span>
                      <span className="score-denom">/10</span>
                    </div>
                    <div className="overall-score-right">
                      <span className={`score-badge ${feedback.overall_label}`}>{feedback.overall_label}</span>
                      <div className="overall-bar-wrap">
                        <div className={`overall-bar ${feedback.overall_label}`} style={{width: `${Number(feedback.overall_score) * 10}%`}} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Approval likelihood */}
                <div className="likelihood-block">
                  <span className="block-label">Approval Likelihood</span>
                  <div className="likelihood-number-row">
                    <span className={`likelihood-pct ${
                      feedback.approval_likelihood >= 70 ? 'likely' :
                      feedback.approval_likelihood >= 40 ? 'borderline' : 'unlikely'
                    }`}>{feedback.approval_likelihood}%</span>
                    <span className="likelihood-label-text">
                      {feedback.approval_likelihood >= 70 ? 'Likely to be Approved' :
                       feedback.approval_likelihood >= 40 ? 'Borderline — Needs Work' :
                       'Unlikely to be Approved'}
                    </span>
                  </div>
                  <div className="likelihood-bar-wrap">
                    <div className={`likelihood-bar ${
                      feedback.approval_likelihood >= 70 ? 'likely' :
                      feedback.approval_likelihood >= 40 ? 'borderline' : 'unlikely'
                    }`} style={{width: `${feedback.approval_likelihood}%`}} />
                  </div>
                </div>
              </div>
            </div>

            {/* ── Critical gaps banner ── */}
            {feedback.critical_gaps?.length > 0 && (
              <div className="critical-gaps">
                <AlertTriangle size={14} />
                <span className="gaps-label">Critical Gaps:</span>
                {feedback.critical_gaps.map(g => (
                  <span key={g} className="gap-chip">{g}</span>
                ))}
              </div>
            )}

            {/* ── Per-dimension cards ── */}
            {['relevance', 'depth', 'precision', 'outcomes', 'coverage'].map(dim => {
              const d = feedback[dim];
              if (!d) return null;
              return (
                <div key={dim} className={`dim-card ${d.label}`}>
                  <div className="dim-header">
                    <div className="dim-title">
                      <h3>{DIM_LABELS[dim]}</h3>
                      <p className="dim-desc">{DIM_DESC[dim]}</p>
                    </div>
                    <div className="dim-score-block">
                      <span className={`label-pill ${d.label}`}>{d.label}</span>
                      <span className="dim-score">
                        {d.score}<span className="dim-score-denom">/10</span>
                      </span>
                    </div>
                  </div>

                  <div className="score-bar-wrap">
                    <div className={`score-bar ${d.label}`} style={{width: `${d.score * 10}%`}} />
                  </div>

                  <div className="rationale-block">
                    <span className="block-label">Analysis</span>
                    <p className="rationale-text">
                      {d.rationale && d.rationale !== '[]' && d.rationale.trim()
                        ? d.rationale
                        : 'No detailed rationale was generated for this dimension.'}
                    </p>
                  </div>

                  {d.suggestion && (
                    <div className="suggestion-box">
                      <span className="block-label">Action Required</span>
                      <p>{d.suggestion}</p>
                    </div>
                  )}
                </div>
              );
            })}

            {/* ── RAG sources ── */}
            {feedback.rag_sources?.length > 0 && (
              <div className="rag-sources">
                <span className="block-label"><Link2 size={11} style={{verticalAlign:'middle', marginRight:'4px'}}/>Reference Sources</span>
                <div className="rag-sources-list">
                  {feedback.rag_sources.map((s, i) => (
                    <div key={i} className="rag-source-row">
                      <span className="rag-tool">{s.tool_name}</span>
                      <span className="rag-heading">{s.heading}</span>
                      <span className="rag-sim">{s.similarity}% match</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Top recommendations ── */}
            {feedback.top_suggestions?.length > 0 && (
              <div className="top-suggestions">
                <span className="block-label"><Zap size={11} style={{verticalAlign:'middle', marginRight:'4px'}}/>Top Recommendations</span>
                <ul>
                  {feedback.top_suggestions.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* ── Shareable summary ── */}
            <div className="shareable-summary">
              <div className="shareable-summary-header">
                <span className="block-label" style={{marginBottom:0}}>Shareable Summary</span>
                <button className={`copy-btn ${copied ? 'copied' : ''}`} onClick={handleCopy} title="Copy to clipboard">
                  {copied ? <><ClipboardCheck size={14}/> Copied!</> : <><Copy size={14}/> Copy Report</>}
                </button>
              </div>
              <pre className="shareable-text">{buildShareableText(feedback)}</pre>
            </div>

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

      {/* BOTTOM: CORPUS */}
      <div className="corpus-section">
        <div className="corpus-header">
          <div className="corpus-title">
            <BookOpen size={18} />
            <h2>Training Corpus</h2>
            {corpus && (
              <span className="corpus-stats">
                <Layers size={12} /> {corpus.total_tools} reports &nbsp;·&nbsp; {corpus.total_chunks} chunks
              </span>
            )}
          </div>
          <div style={{display:'flex', gap:'0.5rem'}}>
            <button
              className="corpus-toggle-btn"
              onClick={() => {
                if (!showCorpus) fetchCorpus();
                setShowCorpus(v => !v);
              }}
            >
              {showCorpus ? 'Hide Reports' : 'View Reports'}
            </button>
            {showCorpus && (
              <button className="corpus-refresh" onClick={fetchCorpus} title="Refresh">
                <RefreshCw size={14} />
              </button>
            )}
          </div>
        </div>

        {showCorpus && !corpus && (
          <p className="corpus-empty">Loading corpus...</p>
        )}

        {showCorpus && corpus && corpus.tools.length === 0 && (
          <p className="corpus-empty">No reports ingested yet.</p>
        )}

        {showCorpus && corpus && corpus.tools.length > 0 && (
          <div className="corpus-table">
            <div className="corpus-row corpus-row-head">
              <span>Tool Name</span>
              <span>Category</span>
              <span>Date Added</span>
            </div>
            {corpus.tools.map((t, i) => (
              <div key={i} className="corpus-row corpus-row-deletable">
                <span className="corpus-tool-name">{t.tool_name}</span>
                <span className="corpus-category">{t.tool_category}</span>
                <span className="corpus-date-cell">
                  <span className="corpus-date">{t.review_date}</span>
                  <button className="corpus-delete-btn" onClick={() => handleDeleteTool(t.tool_name)} title="Remove from corpus">
                    <Trash2 size={13} />
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* BOTTOM: EVALUATION HISTORY */}
      <div className="corpus-section">
        <div className="corpus-header">
          <div className="corpus-title">
            <CheckCircle size={18} />
            <h2>Evaluation History</h2>
            {history && (
              <span className="corpus-stats">
                <Layers size={12} /> {history.total} evaluations
              </span>
            )}
          </div>
          <div style={{display:'flex', gap:'0.5rem'}}>
            <button className="corpus-toggle-btn" onClick={() => { if (!showHistory) fetchHistory(); setShowHistory(v => !v); }}>
              {showHistory ? 'Hide History' : 'View History'}
            </button>
            {showHistory && (
              <button className="corpus-refresh" onClick={fetchHistory} title="Refresh">
                <RefreshCw size={14} />
              </button>
            )}
          </div>
        </div>

        {showHistory && history && history.entries.length === 0 && (
          <p className="corpus-empty">No evaluations yet. Run your first evaluation above.</p>
        )}

        {showHistory && history && history.entries.length > 0 && (
          <div className="corpus-table">
            <div className="corpus-row history-row-head">
              <span>Tool Name</span>
              <span>Category</span>
              <span>Score</span>
              <span>Likelihood</span>
              <span>Status</span>
              <span>Evaluated</span>
            </div>
            {history.entries.map((e) => (
              <div key={e.review_id} className="corpus-row history-row">
                <span className="corpus-tool-name">{e.tool_name}</span>
                <span className="corpus-category">{e.tool_category}</span>
                <span className={`history-score ${e.overall_label}`}>{Number(e.overall_score).toFixed(1)}/10</span>
                <span className={`history-likelihood ${
                  e.approval_likelihood >= 70 ? 'likely' :
                  e.approval_likelihood >= 40 ? 'borderline' : 'unlikely'
                }`}>{e.approval_likelihood}%</span>
                <span className={`label-pill ${e.disposition}`}>{e.disposition}</span>
                <span className="corpus-date">{new Date(e.evaluated_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}

export default App;
