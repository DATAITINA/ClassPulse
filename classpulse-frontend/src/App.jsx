import { useCallback, useEffect, useMemo, useState } from 'react'
import './App.css'
import classpulseLogo from './assets/classpulse-logo.png'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8000'
const STORAGE_KEY = 'classpulse_session_token'

const defaultInsights = {
  course_id: null,
  course_title: null,
  total_feedback: 0,
  sentiment_breakdown: { positive: 0, neutral: 0, negative: 0 },
  top_issues: [],
  top_strengths: [],
  top_recommendations: [],
  fair_view: {
    enough_data: false,
    minimum_responses: 3,
    fairness_note: 'No course data yet.',
  },
  pulse_overview: {
    mood_before_breakdown: {},
    mood_after_breakdown: {},
    average_mood_shift: 0,
  },
  response_loop_summary: {
    total_responses: 0,
    helped_count: 0,
    average_heard_rating: 0,
  },
}

const emptyHealth = {
  course_id: null,
  course_title: '',
  active_reflections: 0,
  total_feedback: 0,
  total_response_loops: 0,
  helpful_response_rate: 0,
  average_heard_rating: 0,
  pulse_shift_average: 0,
  trust_signal: 'Relationship data will appear after students and lecturers begin using the loop.',
}

const moodOptions = ['stressed', 'bored', 'confused', 'calm', 'engaged', 'excited']

const navByRole = {
  student: [
    { id: 'overview', label: 'Overview' },
    { id: 'voice', label: 'Give Voice' },
    { id: 'loop', label: 'Response Loop' },
    { id: 'insights', label: 'Insights' },
  ],
  lecturer: [
    { id: 'overview', label: 'Overview' },
    { id: 'studio', label: 'Course Studio' },
    { id: 'loop', label: 'Response Loop' },
    { id: 'insights', label: 'Insights' },
  ],
  admin: [
    { id: 'overview', label: 'Overview' },
    { id: 'studio', label: 'Course Studio' },
    { id: 'loop', label: 'Response Loop' },
    { id: 'insights', label: 'Insights' },
  ],
}

function formatPercent(value, total) {
  if (!total) {
    return '0%'
  }
  return `${Math.round((value / total) * 100)}%`
}

function titleCase(value) {
  if (!value) return ''
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function getDefaultViewForRole(role) {
  return role === 'student' ? 'voice' : 'studio'
}

function App() {
  const [sessionToken, setSessionToken] = useState(() => localStorage.getItem(STORAGE_KEY) || '')
  const [currentUser, setCurrentUser] = useState(null)
  const [activeView, setActiveView] = useState('overview')
  const [authMode, setAuthMode] = useState('register')
  const [authForm, setAuthForm] = useState({
    name: '',
    email: '',
    password: '',
    role: 'student',
    institution: '',
  })
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)

  const [courses, setCourses] = useState([])
  const [selectedCourseId, setSelectedCourseId] = useState(null)
  const [courseForm, setCourseForm] = useState({ title: '', code: '', description: '' })
  const [joinCode, setJoinCode] = useState('')
  const [courseActionError, setCourseActionError] = useState('')
  const [courseActionSuccess, setCourseActionSuccess] = useState('')
  const [courseActionLoading, setCourseActionLoading] = useState(false)

  const [insights, setInsights] = useState(defaultInsights)
  const [relationshipHealth, setRelationshipHealth] = useState(emptyHealth)
  const [reflections, setReflections] = useState([])
  const [workspaceLoading, setWorkspaceLoading] = useState(false)
  const [workspaceError, setWorkspaceError] = useState('')

  const [feedbackForm, setFeedbackForm] = useState({
    feedback_text: '',
    mood_before: '',
    mood_after: '',
  })
  const [analysis, setAnalysis] = useState(null)
  const [feedbackError, setFeedbackError] = useState('')
  const [feedbackSuccess, setFeedbackSuccess] = useState('')
  const [feedbackLoading, setFeedbackLoading] = useState(false)

  const [reflectionForm, setReflectionForm] = useState({
    headline: '',
    what_i_heard: '',
    what_i_will_change: '',
  })
  const [reflectionError, setReflectionError] = useState('')
  const [reflectionSuccess, setReflectionSuccess] = useState('')
  const [reflectionLoading, setReflectionLoading] = useState(false)

  const [responseDrafts, setResponseDrafts] = useState({})
  const [responseError, setResponseError] = useState('')
  const [responseSuccess, setResponseSuccess] = useState('')
  const [responseLoadingId, setResponseLoadingId] = useState(null)

  const selectedCourse = useMemo(
    () => courses.find((course) => course.id === selectedCourseId) ?? null,
    [courses, selectedCourseId],
  )
  const hasSelectedCourse = Boolean(selectedCourse)

  const currentNav = navByRole[currentUser?.role ?? 'student']
  const resolvedActiveView = currentNav.some((item) => item.id === activeView)
    ? activeView
    : getDefaultViewForRole(currentUser?.role ?? 'student')

  const apiFetch = useCallback(
    async (path, options = {}) => {
      const headers = {
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers ?? {}),
      }

      if (sessionToken) {
        headers.Authorization = `Bearer ${sessionToken}`
      }

      const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
      })

      const contentType = response.headers.get('content-type') || ''
      const data = contentType.includes('application/json') ? await response.json() : null

      if (!response.ok) {
        throw new Error(data?.detail || 'Something went wrong.')
      }

      return data
    },
    [sessionToken],
  )

  const refreshCourseData = useCallback(
    async (courseId) => {
      if (!courseId || !sessionToken) {
        setInsights(defaultInsights)
        setRelationshipHealth(emptyHealth)
        setReflections([])
        return
      }

      setWorkspaceLoading(true)
      setWorkspaceError('')

      try {
        const [insightData, healthData, reflectionData] = await Promise.all([
          apiFetch(`/insights?course_id=${courseId}`),
          apiFetch(`/relationship-health?course_id=${courseId}`),
          apiFetch(`/reflections?course_id=${courseId}`),
        ])
        setInsights(insightData)
        setRelationshipHealth(healthData)
        setReflections(reflectionData)
      } catch (error) {
        setWorkspaceError(error.message)
      } finally {
        setWorkspaceLoading(false)
      }
    },
    [apiFetch, sessionToken],
  )

  const loadWorkspace = useCallback(async () => {
    if (!sessionToken) {
      return
    }

    setWorkspaceLoading(true)
    setWorkspaceError('')

    try {
      const [meData, courseData] = await Promise.all([apiFetch('/me'), apiFetch('/courses')])
      setCurrentUser(meData)
      setCourses(courseData)
      setActiveView((current) => {
        const allowedViews = navByRole[meData.role]?.map((item) => item.id) ?? ['overview']
        if (!allowedViews.includes(current)) {
          return getDefaultViewForRole(meData.role)
        }
        if (!courseData.length && current === 'overview') {
          return getDefaultViewForRole(meData.role)
        }
        return current
      })

      if (courseData.length) {
        setSelectedCourseId((current) =>
          courseData.some((course) => course.id === current) ? current : courseData[0].id,
        )
      } else {
        setSelectedCourseId(null)
        setInsights(defaultInsights)
        setRelationshipHealth(emptyHealth)
        setReflections([])
      }
    } catch (error) {
      localStorage.removeItem(STORAGE_KEY)
      setSessionToken('')
      setCurrentUser(null)
      setCourses([])
      setWorkspaceError(error.message)
    } finally {
      setWorkspaceLoading(false)
    }
  }, [apiFetch, sessionToken])

  useEffect(() => {
    if (sessionToken) {
      const timeoutId = window.setTimeout(() => {
        void loadWorkspace()
      }, 0)
      return () => window.clearTimeout(timeoutId)
    }
  }, [loadWorkspace, sessionToken])

  useEffect(() => {
    if (selectedCourseId) {
      const timeoutId = window.setTimeout(() => {
        void refreshCourseData(selectedCourseId)
      }, 0)
      return () => window.clearTimeout(timeoutId)
    }
  }, [refreshCourseData, selectedCourseId])

  function updateAuthField(event) {
    const { name, value } = event.target
    setAuthForm((current) => ({ ...current, [name]: value }))
  }

  async function handleAuthSubmit(event) {
    event.preventDefault()
    setAuthError('')
    setAuthLoading(true)

    const path = authMode === 'register' ? '/auth/register' : '/auth/login'
    const body =
      authMode === 'register'
        ? authForm
        : { email: authForm.email, password: authForm.password }

    try {
      const data = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(async (response) => {
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail || 'Unable to continue.')
        }
        return payload
      })

      localStorage.setItem(STORAGE_KEY, data.token)
      setSessionToken(data.token)
      setCurrentUser(data.user)
      setAuthForm({
        name: '',
        email: '',
        password: '',
        role: 'student',
        institution: '',
      })
      setActiveView(getDefaultViewForRole(data.user.role))
    } catch (error) {
      setAuthError(error.message)
    } finally {
      setAuthLoading(false)
    }
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY)
    setSessionToken('')
    setCurrentUser(null)
    setCourses([])
    setSelectedCourseId(null)
    setInsights(defaultInsights)
    setRelationshipHealth(emptyHealth)
    setReflections([])
    setAnalysis(null)
    setActiveView('overview')
  }

  function updateCourseField(event) {
    const { name, value } = event.target
    setCourseForm((current) => ({ ...current, [name]: value }))
  }

  async function handleCreateCourse(event) {
    event.preventDefault()
    setCourseActionError('')
    setCourseActionSuccess('')
    setCourseActionLoading(true)

    try {
      const course = await apiFetch('/courses', {
        method: 'POST',
        body: JSON.stringify(courseForm),
      })
      setCourseForm({ title: '', code: '', description: '' })
      await loadWorkspace()
      setSelectedCourseId(course.id)
      setActiveView('studio')
      setCourseActionSuccess(`Course created. Share join code ${course.join_code} with students.`)
    } catch (error) {
      setCourseActionError(error.message)
    } finally {
      setCourseActionLoading(false)
    }
  }

  async function handleJoinCourse(event) {
    event.preventDefault()
    setCourseActionError('')
    setCourseActionSuccess('')
    setCourseActionLoading(true)

    try {
      const normalizedJoinCode = joinCode.trim().toUpperCase()
      const course = await apiFetch('/courses/join', {
        method: 'POST',
        body: JSON.stringify({ join_code: normalizedJoinCode }),
      })
      setJoinCode('')
      await loadWorkspace()
      setSelectedCourseId(course.id)
      setActiveView('voice')
      setCourseActionSuccess(`Joined ${course.code} successfully.`)
    } catch (error) {
      setCourseActionError(error.message)
    } finally {
      setCourseActionLoading(false)
    }
  }

  function updateFeedbackField(event) {
    const { name, value } = event.target
    setFeedbackForm((current) => ({ ...current, [name]: value }))
  }

  async function handleFeedbackSubmit(event) {
    event.preventDefault()
    if (!selectedCourse) {
      setFeedbackError('Join a course first before sending feedback.')
      return
    }

    setFeedbackError('')
    setFeedbackSuccess('')
    setFeedbackLoading(true)
    setAnalysis(null)

    try {
      const result = await apiFetch('/feedback', {
        method: 'POST',
        body: JSON.stringify({
          course_id: selectedCourse.id,
          ...feedbackForm,
        }),
      })
      setAnalysis(result)
      if (result.accepted) {
        setFeedbackForm({ feedback_text: '', mood_before: '', mood_after: '' })
        setFeedbackSuccess('Feedback analyzed and added to this course.')
        await refreshCourseData(selectedCourse.id)
      } else {
        setFeedbackSuccess('Your draft was reviewed, but it needs a respectful rewrite before it can be stored.')
      }
    } catch (error) {
      setFeedbackError(error.message)
    } finally {
      setFeedbackLoading(false)
    }
  }

  function updateReflectionField(event) {
    const { name, value } = event.target
    setReflectionForm((current) => ({ ...current, [name]: value }))
  }

  async function handleReflectionSubmit(event) {
    event.preventDefault()
    if (!selectedCourse) {
      setReflectionError('Create or select a course first.')
      return
    }

    setReflectionError('')
    setReflectionSuccess('')
    setReflectionLoading(true)

    try {
      await apiFetch('/reflections', {
        method: 'POST',
        body: JSON.stringify({
          course_id: selectedCourse.id,
          ...reflectionForm,
        }),
      })
      setReflectionForm({
        headline: '',
        what_i_heard: '',
        what_i_will_change: '',
      })
      setReflectionSuccess('Reflection published. Students can now respond in BridgeLoop.')
      await refreshCourseData(selectedCourse.id)
      setActiveView('loop')
    } catch (error) {
      setReflectionError(error.message)
    } finally {
      setReflectionLoading(false)
    }
  }

  function updateResponseDraft(reflectionId, field, value) {
    setResponseDrafts((current) => ({
      ...current,
      [reflectionId]: {
        helped: true,
        heard_rating: 4,
        comment: '',
        ...(current[reflectionId] ?? {}),
        [field]: value,
      },
    }))
  }

  async function handleResponseLoopSubmit(reflectionId) {
    setResponseError('')
    setResponseSuccess('')
    setResponseLoadingId(reflectionId)

    const draft = responseDrafts[reflectionId] ?? {
      helped: true,
      heard_rating: 4,
      comment: '',
    }

    try {
      await apiFetch('/response-loops', {
        method: 'POST',
        body: JSON.stringify({
          reflection_id: reflectionId,
          helped: draft.helped,
          heard_rating: Number(draft.heard_rating),
          comment: draft.comment,
        }),
      })
      if (selectedCourse) {
        await refreshCourseData(selectedCourse.id)
      }
      setResponseSuccess('Your response has been recorded in the loop.')
    } catch (error) {
      setResponseError(error.message)
    } finally {
      setResponseLoadingId(null)
    }
  }

  if (!currentUser) {
    return (
      <div className="auth-shell">
        <section className="auth-story">
          <div className="brand-hero">
            <img src={classpulseLogo} alt="ClassPulse logo" />
            <div>
              <p className="eyebrow">ClassPulse</p>
              <h1>Build trust between students and lecturers, not just reports.</h1>
            </div>
          </div>

          <p className="auth-copy">
            ClassPulse is a verified-anonymous classroom relationship system. Students get a
            safe place to speak, lecturers get actionable insight, and both sides can close
            the loop together through visible reflection and response.
          </p>

          <div className="auth-pill-row">
            <span>VoiceSafe moderation</span>
            <span>PulseCheck moods</span>
            <span>FairView safeguards</span>
            <span>ResponseLoop repair</span>
          </div>
        </section>

        <section className="auth-panel">
          <div className="auth-toggle">
            <button
              className={authMode === 'register' ? 'toggle-chip active' : 'toggle-chip'}
              onClick={() => setAuthMode('register')}
            >
              Create account
            </button>
            <button
              className={authMode === 'login' ? 'toggle-chip active' : 'toggle-chip'}
              onClick={() => setAuthMode('login')}
            >
              Sign in
            </button>
          </div>

          <form className="auth-form" onSubmit={handleAuthSubmit}>
            {authMode === 'register' && (
              <>
                <label>
                  Full name
                  <input
                    name="name"
                    value={authForm.name}
                    onChange={updateAuthField}
                    placeholder="Amina Yusuf"
                    required
                  />
                </label>

                <label>
                  Role
                  <select name="role" value={authForm.role} onChange={updateAuthField}>
                    <option value="student">Student</option>
                    <option value="lecturer">Lecturer</option>
                  </select>
                </label>

                <label>
                  Institution
                  <input
                    name="institution"
                    value={authForm.institution}
                    onChange={updateAuthField}
                    placeholder="Future University"
                  />
                </label>
              </>
            )}

            <label>
              Email
              <input
                name="email"
                type="email"
                value={authForm.email}
                onChange={updateAuthField}
                placeholder="you@example.com"
                required
              />
            </label>

            <label>
              Password
              <input
                name="password"
                type="password"
                value={authForm.password}
                onChange={updateAuthField}
                placeholder="At least 6 characters"
                required
              />
            </label>

            {authError ? <p className="message error">{authError}</p> : null}

            <button className="button button-primary" disabled={authLoading}>
              {authLoading
                ? 'Working...'
                : authMode === 'register'
                  ? 'Enter ClassPulse'
                  : 'Continue to workspace'}
            </button>
          </form>
        </section>
      </div>
    )
  }

  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <div className="workspace-brand">
          <img src={classpulseLogo} alt="ClassPulse logo" />
          <div>
            <p className="eyebrow">ClassPulse workspace</p>
            <h1>Relationship intelligence for real classrooms.</h1>
          </div>
        </div>

        <div className="header-meta">
          <span className={`role-pill role-${currentUser.role}`}>{titleCase(currentUser.role)}</span>
          <button className="button button-secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="workspace-nav" aria-label="Primary">
        {currentNav.map((item) => (
          <button
            key={item.id}
            className={resolvedActiveView === item.id ? 'nav-chip active' : 'nav-chip'}
            onClick={() => setActiveView(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="workspace-grid">
        <aside className="sidebar">
          <section className="sidebar-card">
            <div className="sidebar-heading">
              <p className="eyebrow">Your courses</p>
              <strong>{courses.length}</strong>
            </div>

            <div className="course-list">
              {courses.length ? (
                courses.map((course) => (
                  <button
                    key={course.id}
                    className={selectedCourseId === course.id ? 'course-chip active' : 'course-chip'}
                    onClick={() => setSelectedCourseId(course.id)}
                  >
                    <span>{course.code}</span>
                    <small>{course.title}</small>
                  </button>
                ))
              ) : (
                <p className="muted">No courses yet. Start by creating or joining one.</p>
              )}
            </div>
          </section>

          {selectedCourse ? (
            <section className="sidebar-card">
              <p className="eyebrow">Selected course</p>
              <div className="selected-course-card">
                <strong>{selectedCourse.title}</strong>
                <span>{selectedCourse.code}</span>
                <small>{selectedCourse.member_count} student members</small>
                {currentUser.role !== 'student' && selectedCourse.join_code ? (
                  <small>Join code: {selectedCourse.join_code}</small>
                ) : null}
              </div>
            </section>
          ) : null}

          <section className="sidebar-card">
            <p className="eyebrow">
              {currentUser.role === 'student' ? 'Join a class' : 'Create a class'}
            </p>

            {currentUser.role === 'student' ? (
              <form className="stack-form" onSubmit={handleJoinCourse}>
                <input
                  value={joinCode}
                  onChange={(event) => setJoinCode(event.target.value.toUpperCase())}
                  placeholder="Paste a join code"
                  required
                />
                <button
                  className="button button-primary"
                  disabled={courseActionLoading || !joinCode.trim()}
                >
                  {courseActionLoading ? 'Joining...' : 'Join course'}
                </button>
              </form>
            ) : (
              <form className="stack-form" onSubmit={handleCreateCourse}>
                <input
                  name="title"
                  value={courseForm.title}
                  onChange={updateCourseField}
                  placeholder="Course title"
                  required
                />
                <input
                  name="code"
                  value={courseForm.code}
                  onChange={(event) =>
                    setCourseForm((current) => ({ ...current, code: event.target.value.toUpperCase() }))
                  }
                  placeholder="Course code"
                  required
                />
                <textarea
                  name="description"
                  value={courseForm.description}
                  onChange={updateCourseField}
                  placeholder="What kind of learning space are you building?"
                  rows="4"
                />
                <button className="button button-primary" disabled={courseActionLoading}>
                  {courseActionLoading ? 'Creating...' : 'Create course'}
                </button>
              </form>
            )}

            {courseActionError ? <p className="message error">{courseActionError}</p> : null}
            {courseActionSuccess ? <p className="message success">{courseActionSuccess}</p> : null}
          </section>

          <section className="sidebar-card">
            <p className="eyebrow">Common ground</p>
            <p className="muted">
              Students stay shielded, lecturers stay heard, and the class grows through a
              visible repair loop rather than one-off complaints.
            </p>
          </section>
        </aside>

        <main className="main-panel">
          {workspaceError ? <p className="message error">{workspaceError}</p> : null}

          <>
            {resolvedActiveView === 'overview' && (
              hasSelectedCourse ? (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Selected course</p>
                      <h2>{selectedCourse.title}</h2>
                      <p className="section-copy">
                        {selectedCourse.description || 'A shared course space for voice, reflection, and repair.'}
                      </p>
                    </div>
                    <div className="course-meta-card">
                      <span>{selectedCourse.code}</span>
                      <strong>{selectedCourse.lecturer_name}</strong>
                      {currentUser.role !== 'student' ? (
                        <small>Join code: {selectedCourse.join_code}</small>
                      ) : null}
                    </div>
                  </div>

                  <div className="metric-grid">
                    <article className="metric-card">
                      <span>Total feedback</span>
                      <strong>{workspaceLoading ? '...' : insights.total_feedback}</strong>
                    </article>
                    <article className="metric-card">
                      <span>Helpful response rate</span>
                      <strong>
                        {workspaceLoading ? '...' : `${relationshipHealth.helpful_response_rate}%`}
                      </strong>
                    </article>
                    <article className="metric-card">
                      <span>Average heard rating</span>
                      <strong>
                        {workspaceLoading ? '...' : relationshipHealth.average_heard_rating}
                      </strong>
                    </article>
                  </div>

                  <div className="split-grid">
                    <article className="content-card">
                      <p className="eyebrow">FairView</p>
                      <h3>{insights.fair_view.enough_data ? 'Pattern-ready insight' : 'Protected early-stage insight'}</h3>
                      <p>{insights.fair_view.fairness_note}</p>
                    </article>

                    <article className="content-card">
                      <p className="eyebrow">Trust signal</p>
                      <h3>Relationship health</h3>
                      <p>{relationshipHealth.trust_signal}</p>
                    </article>
                  </div>
                </section>
              ) : (
                <section className="view-panel">
                  <EmptyStateCard
                    eyebrow="Workspace ready"
                    title={
                      currentUser.role === 'student'
                        ? 'You are inside ClassPulse. Now connect to a class.'
                        : 'You are inside ClassPulse. Now open your first course space.'
                    }
                    body={
                      currentUser.role === 'student'
                        ? 'Switch to Give Voice to paste a lecturer join code and unlock your classroom space.'
                        : 'Switch to Course Studio to create a course, get a join code, and invite students into a healthy feedback loop.'
                    }
                    actions={
                      currentUser.role === 'student'
                        ? (
                            <button className="button button-primary" onClick={() => setActiveView('voice')}>
                              Go to Give Voice
                            </button>
                          )
                        : (
                            <button className="button button-primary" onClick={() => setActiveView('studio')}>
                              Open Course Studio
                            </button>
                          )
                    }
                  />

                  <div className="split-grid">
                    <article className="content-card">
                      <p className="eyebrow">What ClassPulse does</p>
                      <h3>Feedback becomes a visible repair loop.</h3>
                      <ul className="plain-list">
                        <li>Verified-anonymous feedback protects the student voice.</li>
                        <li>VoiceSafe nudges feedback into respectful, useful language.</li>
                        <li>Lecturer reflections create a response loop instead of silent frustration.</li>
                      </ul>
                    </article>

                    <article className="content-card">
                      <p className="eyebrow">Next step</p>
                      <h3>{currentUser.role === 'student' ? 'Get a join code from your lecturer.' : 'Create a course and share the code.'}</h3>
                      <p className="muted">
                        {currentUser.role === 'student'
                          ? 'Once you join a course, Give Voice, Response Loop, and Insights will all attach to that live classroom.'
                          : 'Once a course exists, students can join, send feedback, and you can start publishing reflections.'}
                      </p>
                    </article>
                  </div>
                </section>
              )
            )}

            {resolvedActiveView === 'voice' && currentUser.role === 'student' && (
              hasSelectedCourse ? (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Verified anonymous voice</p>
                      <h2>Share what class feels like from the inside.</h2>
                      <p className="section-copy">
                        Your identity is verified for trust, but the lecturer only receives an anonymous
                        class voice alias and the pattern behind your feedback.
                      </p>
                    </div>
                  </div>

                  <div className="split-grid">
                    <form className="content-card stack-form" onSubmit={handleFeedbackSubmit}>
                      <label>
                        Mood before class
                        <select
                          name="mood_before"
                          value={feedbackForm.mood_before}
                          onChange={updateFeedbackField}
                        >
                          <option value="">Optional</option>
                          {moodOptions.map((mood) => (
                            <option key={mood} value={mood}>
                              {titleCase(mood)}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label>
                        Mood after class
                        <select
                          name="mood_after"
                          value={feedbackForm.mood_after}
                          onChange={updateFeedbackField}
                        >
                          <option value="">Optional</option>
                          {moodOptions.map((mood) => (
                            <option key={mood} value={mood}>
                              {titleCase(mood)}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label>
                        What should this lecturer understand?
                        <textarea
                          name="feedback_text"
                          value={feedbackForm.feedback_text}
                          onChange={updateFeedbackField}
                          rows="8"
                          placeholder="The examples are clear, but the pace becomes too fast when the class moves into harder concepts."
                          required
                        />
                      </label>

                      {feedbackError ? <p className="message error">{feedbackError}</p> : null}
                      {feedbackSuccess ? <p className="message success">{feedbackSuccess}</p> : null}

                      <button className="button button-primary" disabled={feedbackLoading}>
                        {feedbackLoading ? 'Analyzing...' : 'Send feedback'}
                      </button>
                    </form>

                    <div className="content-card">
                      <p className="eyebrow">InsightLens result</p>

                      {!analysis ? (
                        <div className="empty-note">
                          <h3>No analysis yet</h3>
                          <p>Submit one real classroom reflection and ClassPulse will structure the signal here.</p>
                        </div>
                      ) : (
                        <div className="analysis-stack">
                          <div className="result-pill-row">
                            <span className={`status-token status-${analysis.moderation_status}`}>
                              {analysis.moderation_status}
                            </span>
                            <span className="status-token neutral">{analysis.sentiment}</span>
                          </div>

                          {analysis.anonymous_alias ? (
                            <p className="muted">Visible to lecturer as: {analysis.anonymous_alias}</p>
                          ) : null}

                          <p>{analysis.moderation_message}</p>

                          {analysis.respectful_rewrite ? (
                            <div className="nested-card">
                              <strong>Respectful rewrite</strong>
                              <p>{analysis.respectful_rewrite}</p>
                            </div>
                          ) : null}

                          <ListSection title="Strengths" items={analysis.strengths} />
                          <ListSection title="Key issues" items={analysis.key_issues} />
                          <ListSection title="Suggestions" items={analysis.suggestions} />

                          {analysis.next_step_ai ? (
                            <div className="nested-card">
                              <strong>NextStep AI</strong>
                              <p>{analysis.next_step_ai}</p>
                            </div>
                          ) : null}
                        </div>
                      )}
                    </div>
                  </div>
                </section>
              ) : (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Verified anonymous voice</p>
                      <h2>Join a course to unlock feedback for a real class.</h2>
                      <p className="section-copy">
                        The tab is working. The next thing ClassPulse needs is a valid lecturer join code so your voice has a classroom to land in.
                      </p>
                    </div>
                  </div>

                  <div className="split-grid">
                    <article className="content-card stack-form">
                      <label>
                        Paste your class join code
                        <input
                          value={joinCode}
                          onChange={(event) => setJoinCode(event.target.value.toUpperCase())}
                          placeholder="For example: CP7M4Q"
                        />
                      </label>

                      <button
                        className="button button-primary"
                        onClick={handleJoinCourse}
                        disabled={courseActionLoading || !joinCode.trim()}
                      >
                        {courseActionLoading ? 'Joining...' : 'Join this course'}
                      </button>

                      {courseActionError ? <p className="message error">{courseActionError}</p> : null}
                    </article>

                    <article className="content-card">
                      <p className="eyebrow">What happens after you join</p>
                      <h3>Your full voice workspace opens up.</h3>
                      <ul className="plain-list">
                        <li>You can submit moderated, verified-anonymous classroom feedback.</li>
                        <li>PulseCheck captures how class felt before and after.</li>
                        <li>Response Loop and Insights will switch to the live course automatically.</li>
                      </ul>
                    </article>
                  </div>
                </section>
              )
            )}

            {resolvedActiveView === 'studio' && currentUser.role !== 'student' && (
              hasSelectedCourse ? (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Lecturer reflection studio</p>
                      <h2>Close the loop with a public response to the class.</h2>
                      <p className="section-copy">
                        Publish what you heard and what you will change next. Students can then say whether the response actually helped.
                      </p>
                    </div>
                  </div>

                  <form className="content-card stack-form" onSubmit={handleReflectionSubmit}>
                    <label>
                      Reflection headline
                      <input
                        name="headline"
                        value={reflectionForm.headline}
                        onChange={updateReflectionField}
                        placeholder="I heard the pacing concern"
                        required
                      />
                    </label>

                    <label>
                      What I heard
                      <textarea
                        name="what_i_heard"
                        value={reflectionForm.what_i_heard}
                        onChange={updateReflectionField}
                        rows="5"
                        placeholder="Many of you are following the examples but want more breathing room when concepts become harder."
                        required
                      />
                    </label>

                    <label>
                      What I will change
                      <textarea
                        name="what_i_will_change"
                        value={reflectionForm.what_i_will_change}
                        onChange={updateReflectionField}
                        rows="5"
                        placeholder="Next class I will add one recap checkpoint and a student-led example before moving on."
                        required
                      />
                    </label>

                    {reflectionError ? <p className="message error">{reflectionError}</p> : null}
                    {reflectionSuccess ? <p className="message success">{reflectionSuccess}</p> : null}

                    <button className="button button-primary" disabled={reflectionLoading}>
                      {reflectionLoading ? 'Publishing...' : 'Publish reflection'}
                    </button>
                  </form>
                </section>
              ) : (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Course studio</p>
                      <h2>Create the first classroom space.</h2>
                      <p className="section-copy">
                        Once you create a course, ClassPulse will generate a join code for students and activate the full feedback loop.
                      </p>
                    </div>
                  </div>

                  <div className="split-grid">
                    <article className="content-card">
                      <p className="eyebrow">How it works</p>
                      <ul className="plain-list">
                        <li>Create a course from the left sidebar.</li>
                        <li>Share the generated join code with students.</li>
                        <li>Use this studio to publish reflections after feedback arrives.</li>
                      </ul>
                    </article>

                    <article className="content-card">
                      <p className="eyebrow">Why this matters</p>
                      <h3>ClassPulse only becomes meaningful around a live class.</h3>
                      <p className="muted">
                        Your first course unlocks student voice, classroom insights, and the visible repair loop that makes the product stand out.
                      </p>
                    </article>
                  </div>
                </section>
              )
            )}

            {resolvedActiveView === 'loop' && (
              hasSelectedCourse ? (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">BridgeLoop</p>
                      <h2>Reflection and response, in the same classroom space.</h2>
                      <p className="section-copy">
                        This is the shared ground: lecturers acknowledge what they heard, and students signal whether the response helped.
                      </p>
                    </div>
                  </div>

                  {responseError ? <p className="message error">{responseError}</p> : null}
                  {responseSuccess ? <p className="message success">{responseSuccess}</p> : null}

                  <div className="reflection-list">
                    {reflections.length ? (
                      reflections.map((reflection) => {
                        const draft = responseDrafts[reflection.id] ?? {
                          helped: true,
                          heard_rating: 4,
                          comment: '',
                        }

                        return (
                          <article key={reflection.id} className="content-card reflection-card">
                            <div className="reflection-meta">
                              <div>
                                <p className="eyebrow">Lecturer reflection</p>
                                <h3>{reflection.headline}</h3>
                              </div>
                              <span className="timestamp">
                                {new Date(reflection.created_at).toLocaleDateString()}
                              </span>
                            </div>

                            <div className="reflection-body">
                              <div>
                                <strong>What I heard</strong>
                                <p>{reflection.what_i_heard}</p>
                              </div>
                              <div>
                                <strong>What I will change</strong>
                                <p>{reflection.what_i_will_change}</p>
                              </div>
                            </div>

                            <div className="response-summary">
                              <span>{reflection.response_loop_summary.total_responses} responses</span>
                              <span>{reflection.response_loop_summary.helped_count} found it helpful</span>
                              <span>{reflection.response_loop_summary.average_heard_rating} average heard rating</span>
                            </div>

                            {currentUser.role === 'student' ? (
                              <div className="response-form">
                                <div className="toggle-row">
                                  <label className={draft.helped ? 'toggle-option active' : 'toggle-option'}>
                                    <input
                                      type="radio"
                                      name={`helped-${reflection.id}`}
                                      checked={draft.helped === true}
                                      onChange={() => updateResponseDraft(reflection.id, 'helped', true)}
                                    />
                                    This helped
                                  </label>
                                  <label className={!draft.helped ? 'toggle-option active' : 'toggle-option'}>
                                    <input
                                      type="radio"
                                      name={`helped-${reflection.id}`}
                                      checked={draft.helped === false}
                                      onChange={() => updateResponseDraft(reflection.id, 'helped', false)}
                                    />
                                    Not yet
                                  </label>
                                </div>

                                <label>
                                  How heard do you feel? (1-5)
                                  <select
                                    value={draft.heard_rating}
                                    onChange={(event) =>
                                      updateResponseDraft(reflection.id, 'heard_rating', Number(event.target.value))
                                    }
                                  >
                                    {[1, 2, 3, 4, 5].map((score) => (
                                      <option key={score} value={score}>
                                        {score}
                                      </option>
                                    ))}
                                  </select>
                                </label>

                                <label>
                                  Add context
                                  <textarea
                                    rows="4"
                                    value={draft.comment}
                                    onChange={(event) =>
                                      updateResponseDraft(reflection.id, 'comment', event.target.value)
                                    }
                                    placeholder="The acknowledgement helped, but I still need more practice problems."
                                  />
                                </label>

                                <button
                                  className="button button-primary"
                                  onClick={() => handleResponseLoopSubmit(reflection.id)}
                                  disabled={responseLoadingId === reflection.id}
                                >
                                  {responseLoadingId === reflection.id ? 'Sending...' : 'Send response'}
                                </button>
                              </div>
                            ) : null}
                          </article>
                        )
                      })
                    ) : (
                      <div className="empty-note">
                        <h3>No reflections yet</h3>
                        <p>
                          {currentUser.role === 'student'
                            ? 'The lecturer has not published a reflection yet.'
                            : 'Publish your first reflection from the Course Studio to start the response loop.'}
                        </p>
                      </div>
                    )}
                  </div>
                </section>
              ) : (
                <EmptyStateCard
                  eyebrow="BridgeLoop"
                  title="Response Loop needs a live course first."
                  body={
                    currentUser.role === 'student'
                      ? 'Join a class first. Once a lecturer publishes a reflection, this tab will let you respond and say whether you felt heard.'
                      : 'Create a course first. After students submit feedback and you publish a reflection, this tab becomes the shared repair space.'
                  }
                  actions={
                    <button
                      className="button button-primary"
                      onClick={() =>
                        setActiveView(currentUser.role === 'student' ? 'voice' : 'studio')
                      }
                    >
                      {currentUser.role === 'student' ? 'Go to Give Voice' : 'Open Course Studio'}
                    </button>
                  }
                />
              )
            )}

            {resolvedActiveView === 'insights' && (
              hasSelectedCourse ? (
                <section className="view-panel">
                  <div className="section-header">
                    <div>
                      <p className="eyebrow">Course insights</p>
                      <h2>Fair patterns, not emotional snapshots.</h2>
                      <p className="section-copy">
                        ClassPulse protects both sides by withholding detailed patterns until enough verified student voices are present.
                      </p>
                    </div>
                  </div>

                  <div className="metric-grid">
                    {['positive', 'neutral', 'negative'].map((sentiment) => {
                      const value = insights.sentiment_breakdown[sentiment] ?? 0
                      return (
                        <article key={sentiment} className="metric-card">
                          <span>{titleCase(sentiment)}</span>
                          <strong>{value}</strong>
                          <small>{formatPercent(value, insights.total_feedback)}</small>
                        </article>
                      )
                    })}
                  </div>

                  <div className="split-grid">
                    <ListCard
                      title="Top strengths"
                      subtitle={insights.fair_view.fairness_note}
                      items={insights.top_strengths}
                    />
                    <ListCard
                      title="Top issues"
                      subtitle="What the class is struggling with most often."
                      items={insights.top_issues}
                    />
                  </div>

                  <div className="split-grid">
                    <ListCard
                      title="NextStep AI recommendations"
                      subtitle="The most repeated guidance for the lecturer's next move."
                      items={insights.top_recommendations}
                    />
                    <article className="content-card">
                      <p className="eyebrow">Pulse and response loop</p>
                      <div className="pulse-grid">
                        <div>
                          <strong>{relationshipHealth.pulse_shift_average}</strong>
                          <span>Average mood shift</span>
                        </div>
                        <div>
                          <strong>{relationshipHealth.total_response_loops}</strong>
                          <span>Student follow-up responses</span>
                        </div>
                        <div>
                          <strong>{relationshipHealth.helpful_response_rate}%</strong>
                          <span>Helpful response rate</span>
                        </div>
                        <div>
                          <strong>{relationshipHealth.average_heard_rating}</strong>
                          <span>Average heard rating</span>
                        </div>
                      </div>
                      <p className="trust-copy">{relationshipHealth.trust_signal}</p>
                    </article>
                  </div>
                </section>
              ) : (
                <EmptyStateCard
                  eyebrow="Course insights"
                  title="Insights appear when a class is connected."
                  body="Choose or join a real course first. Then ClassPulse can show FairView patterns, mood shifts, response health, and repeated issues with enough data to be fair."
                  actions={
                    <button
                      className="button button-primary"
                      onClick={() =>
                        setActiveView(currentUser.role === 'student' ? 'voice' : 'studio')
                      }
                    >
                      {currentUser.role === 'student' ? 'Join a course' : 'Create a course'}
                    </button>
                  }
                />
              )
            )}
          </>
        </main>
      </div>
    </div>
  )
}

function ListSection({ title, items }) {
  if (!items?.length) return null

  return (
    <div className="nested-card">
      <strong>{title}</strong>
      <ul className="plain-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

function ListCard({ title, subtitle, items }) {
  return (
    <article className="content-card">
      <p className="eyebrow">{title}</p>
      <p className="muted">{subtitle}</p>
      {items?.length ? (
        <ul className="plain-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="muted">FairView is still collecting enough verified responses for this course.</p>
      )}
    </article>
  )
}

function EmptyStateCard({ eyebrow, title, body, actions = null }) {
  return (
    <section className="empty-panel empty-panel-left">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p>{body}</p>
      {actions ? <div className="empty-actions">{actions}</div> : null}
    </section>
  )
}

export default App
