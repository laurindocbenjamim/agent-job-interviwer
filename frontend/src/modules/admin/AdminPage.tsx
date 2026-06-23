import React, { useState } from 'react';
import './AdminPage.css';

export const AdminPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setLoading(true);
    setStatus('Uploading...');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await fetch('http://localhost:8000/admin/voice/clone', {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        setStatus('Voice cloned successfully! You can now use it in interviews.');
      } else {
        setStatus('Failed to clone voice.');
      }
    } catch (err) {
      console.error(err);
      setStatus('Error connecting to server.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-container">
      <div className="admin-card">
        <h1 className="admin-title">Admin Voice Cloning</h1>
        <p className="admin-subtitle">Upload a clear, 3-10 second audio clip of the recruiter's voice to clone it for the AI Interviewer.</p>
        
        <div className="upload-section">
          <input 
            type="file" 
            accept="audio/*" 
            onChange={handleFileChange} 
            className="file-input"
          />
          <button 
            onClick={handleUpload} 
            disabled={!file || loading}
            className={`btn-primary ${!file || loading ? 'disabled' : ''}`}
          >
            {loading ? 'Uploading...' : 'Clone Voice'}
          </button>
        </div>
        
        {status && <p className="status-message">{status}</p>}
      </div>
    </div>
  );
};
