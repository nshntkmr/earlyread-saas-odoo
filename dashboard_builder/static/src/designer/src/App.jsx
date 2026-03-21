import React, { useState } from 'react'
import Sidebar from './components/Sidebar'
import WidgetLibrary from './components/WidgetLibrary'
import TemplateGallery from './components/TemplateGallery'
import WidgetBuilder from './components/builder/WidgetBuilder'
import '../styles/designer.css'

const VIEWS = {
  library: 'library',
  templates: 'templates',
  create: 'create',
  edit: 'edit',
}

/**
 * Dashboard Designer — Root Component
 *
 * Layout: Sidebar (left) + Main content (right)
 * Views: Widget Library, Templates, Create Widget, Edit Widget
 *
 * Placement is NOT done here — portal admins place widgets
 * from within their app using the "Add from Library" picker.
 */
export default function App({ apiBase, userName }) {
  const [view, setView] = useState(VIEWS.library)
  const [editId, setEditId] = useState(null)

  const handleSaveDone = () => {
    setEditId(null)
    setView(VIEWS.library)
  }

  const handleEdit = (def) => {
    setEditId(def.id)
    setView(VIEWS.edit)
  }

  return (
    <div className="dd-layout">
      <Sidebar
        currentView={view === VIEWS.edit ? VIEWS.library : view}
        onNavigate={(v) => { setEditId(null); setView(v) }}
        userName={userName}
      />
      <main className="dd-main">
        {view === VIEWS.library && (
          <WidgetLibrary
            apiBase={apiBase}
            onCreate={() => setView(VIEWS.create)}
            onEdit={handleEdit}
          />
        )}
        {view === VIEWS.templates && (
          <TemplateGallery
            apiBase={apiBase}
          />
        )}
        {view === VIEWS.create && (
          <WidgetBuilder
            isOpen={true}
            onClose={() => setView(VIEWS.library)}
            onWidgetCreated={handleSaveDone}
            apiBase={apiBase}
          />
        )}
        {view === VIEWS.edit && editId && (
          <WidgetBuilder
            key={`edit-${editId}`}
            isOpen={true}
            onClose={() => { setEditId(null); setView(VIEWS.library) }}
            onWidgetCreated={handleSaveDone}
            apiBase={apiBase}
            editId={editId}
          />
        )}
      </main>
    </div>
  )
}
