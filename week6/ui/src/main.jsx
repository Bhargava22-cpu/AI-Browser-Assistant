import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// StrictMode is omitted because it double-invokes useEffect in dev,
// which prematurely closes the WebSocket and marks tasks as failed.
createRoot(document.getElementById('root')).render(<App />)
