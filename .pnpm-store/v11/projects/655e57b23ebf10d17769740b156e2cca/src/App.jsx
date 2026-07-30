import React, { useState } from 'react'
import Sidebar from './components/Sidebar'
import AppContextBar from './components/AppContextBar'
import WidgetLibrary from './components/WidgetLibrary'
import TemplateGallery from './components/TemplateGallery'
import TemplateWizard from './components/TemplateWizard'
import WidgetBuilder from './components/builder/WidgetBuilder'
import '../styles/designer.css'

const VIEWS = {
  library: 'library',
  templates: 'templates',
  template_wizard: 'template_wizard',
  create: 'create',
  edit: 'edit',
}

/**
 * Dashboard Designer — Root Component
 *
 * Layout: Sidebar (left) + Context Bar (top) + Main content (right)
 * Views: Widget Library, Templates, Template Wizard, Create Widget, Edit Widget
 *
 * AppContextBar provides optional App → Page → Tab scoping that:
 * - Filters library/sources to the selected app
 * - Loads real page filters for preview
 * - Enables "Save & Place" shortcut
 */
export default function App({ apiBase, userName }) {
  const [view, setView] = useState(VIEWS.library)
  const [editId, setEditId] = useState(null)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [appContext, setAppContext] = useState(null) // { app, page, tab } | null

  const handleSaveDone = () => {
    setEditId(null)
    setView(VIEWS.library)
  }

  const handleEdit = (def) => {
    setEditId(def.id)
    setView(VIEWS.edit)
  }

  const handleUseTemplate = (template) => {
    setSelectedTemplate(template)
    setView(VIEWS.template_wizard)
  }

  const handleTemplateWizardClose = () => {
    setSelectedTemplate(null)
    setView(VIEWS.templates)
  }

  const handleTemplateWizardComplete = () => {
    setSelectedTemplate(null)
    setView(VIEWS.library)
  }

  // For sidebar highlight: template_wizard shows as templates
  const sidebarView = view === VIEWS.edit ? VIEWS.library
    : view === VIEWS.template_wizard ? VIEWS.templates
    : view

  return (
    <div className="dd-layout">
      <Sidebar
        currentView={sidebarView}
        onNavigate={(v) => { setEditId(null); setSelectedTemplate(null); setView(v) }}
        userName={userName}
      />
      <div className="dd-main-wrapper">
        <AppContextBar
          apiBase={apiBase}
          appContext={appContext}
          onChange={setAppContext}
        />
        <main className="dd-main">
          {view === VIEWS.library && (
            <WidgetLibrary
              apiBase={apiBase}
              appContext={appContext}
              onCreate={() => setView(VIEWS.create)}
              onEdit={handleEdit}
            />
          )}
          {view === VIEWS.templates && (
            <TemplateGallery
              apiBase={apiBase}
              appContext={appContext}
              onUseTemplate={handleUseTemplate}
            />
          )}
          {view === VIEWS.template_wizard && selectedTemplate && (
            <TemplateWizard
              template={selectedTemplate}
              apiBase={apiBase}
              appContext={appContext}
              onClose={handleTemplateWizardClose}
              onComplete={handleTemplateWizardComplete}
            />
          )}
          {view === VIEWS.create && (
            <WidgetBuilder
              isOpen={true}
              onClose={() => setView(VIEWS.library)}
              onWidgetCreated={handleSaveDone}
              apiBase={apiBase}
              appContext={appContext}
            />
          )}
          {view === VIEWS.edit && editId && (
            <WidgetBuilder
              key={`edit-${editId}`}
              isOpen={true}
              onClose={() => { setEditId(null); setView(VIEWS.library) }}
              onWidgetCreated={handleSaveDone}
              apiBase={apiBase}
              appContext={appContext}
              editId={editId}
            />
          )}
        </main>
      </div>
    </div>
  )
}
