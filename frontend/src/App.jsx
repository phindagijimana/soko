import { useEffect, useMemo, useState } from 'react'
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { api, API_BASE } from './lib/api'
import { emptyListing, emptyOrder, emptyRegister, emptyReview, emptySupport } from './lib/constants'

function SectionTitle({ title, text }) {
  return (
    <div className="section-title">
      <h2>{title}</h2>
      {text ? <p>{text}</p> : null}
    </div>
  )
}

function GateNotice({ title, text, actionText, onAction }) {
  return (
    <div className="gate-notice">
      <h3>{title}</h3>
      <p>{text}</p>
      <button type="button" onClick={onAction}>{actionText}</button>
    </div>
  )
}

export default function App() {
  // -------------------------------------------------------------------------
  // View state and domain data
  // -------------------------------------------------------------------------
  const [view, setView] = useState('market')
  const [listings, setListings] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [reviews, setReviews] = useState([])
  const [orders, setOrders] = useState([])
  const [verificationRequests, setVerificationRequests] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [supportTickets, setSupportTickets] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [registerForm, setRegisterForm] = useState(emptyRegister)
  const [otpPhone, setOtpPhone] = useState('')
  const [otpCode, setOtpCode] = useState('123456')
  const [token, setToken] = useState(localStorage.getItem('agri_token') || '')
  const [currentUser, setCurrentUser] = useState(JSON.parse(localStorage.getItem('agri_user') || 'null'))
  const [listingForm, setListingForm] = useState(emptyListing)
  const [orderForm, setOrderForm] = useState(emptyOrder)
  const [reviewForm, setReviewForm] = useState(emptyReview)
  const [search, setSearch] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [verificationNotes, setVerificationNotes] = useState({})
  const [supportForm, setSupportForm] = useState(emptySupport)
  const [supportNotes, setSupportNotes] = useState({})

  // Derived access helpers
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {}
  const isFarmer = currentUser?.role === 'farmer'
  const isBuyer = currentUser?.role === 'buyer'

  const resetAlerts = () => {
    setError('')
    setMessage('')
  }

  const jumpToAuth = (text = 'Create a profile or sign in with phone OTP to continue.') => {
    setMessage(text)
    setView('auth')
  }

  const recordInteraction = async (interactionType, listingId = null, queryValue = '') => {
    if (!token) return
    try {
      await api('/interactions', {
        method: 'POST',
        headers: authHeaders,
        body: JSON.stringify({ interaction_type: interactionType, listing_id: listingId, query: queryValue || undefined }),
      })
    } catch (err) {
      console.warn('Interaction tracking failed', err)
    }
  }

  const loadRecommendations = async () => {
    try {
      const data = await api('/recommendations', { headers: token ? authHeaders : {} })
      setRecommendations(data)
    } catch (err) {
      setError(err.message)
    }
  }

  const runSearch = async () => {
    resetAlerts()
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('query', search.trim())
      if (locationFilter.trim()) params.set('location', locationFilter.trim())
      const path = `/listings${params.toString() ? `?${params.toString()}` : ''}`
      const data = await api(path, { headers: token ? authHeaders : {} })
      setListings(data)
      await loadRecommendations()
    } catch (err) {
      setError(err.message)
    }
  }

  // Data loading
  const loadPublicData = async () => {
    try {
      const [listingData, reviewData] = await Promise.all([api('/listings'), api('/reviews')])
      setListings(listingData)
      setReviews(reviewData)
      await loadRecommendations()
    } catch (err) {
      setError(err.message)
    }
  }

  const loadPrivateData = async () => {
    if (!token) return
    try {
      const [orderData, me, ticketData] = await Promise.all([
        api('/orders', { headers: authHeaders }),
        api('/me', { headers: authHeaders }),
        api('/support-tickets', { headers: authHeaders }),
      ])
      setOrders(orderData)
      setCurrentUser(me)
      setSupportTickets(ticketData)
      localStorage.setItem('agri_user', JSON.stringify(me))
      if (me.is_admin) {
        const [requests, logs, summary] = await Promise.all([
          api('/admin/verification-requests', { headers: authHeaders }),
          api('/admin/audit-logs', { headers: authHeaders }),
          api('/metrics/summary', { headers: authHeaders }),
        ])
        setVerificationRequests(requests)
        setAuditLogs(logs)
        setMetrics(summary)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    loadPublicData()
  }, [])

  useEffect(() => {
    loadPrivateData()
  }, [token])

  const filteredListings = useMemo(() => listings.filter((listing) => {
    const q = search.toLowerCase()
    const l = locationFilter.toLowerCase()
    const matchesQ = !q || listing.crop.toLowerCase().includes(q) || listing.farmer.name.toLowerCase().includes(q)
    const matchesL = !l || listing.location.toLowerCase().includes(l)
    return matchesQ && matchesL
  }), [listings, search, locationFilter])

  // Auth and profile actions
  const handleRegister = async (e) => {
    e.preventDefault()
    resetAlerts()
    setLoading(true)
    try {
      await api('/users', { method: 'POST', body: JSON.stringify(registerForm) })
      setMessage('Profile created. Request OTP to sign in and continue.')
      setOtpPhone(registerForm.phone)
      setRegisterForm(emptyRegister)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const requestOtp = async () => {
    resetAlerts()
    setLoading(true)
    try {
      const data = await api('/auth/request-otp', { method: 'POST', body: JSON.stringify({ phone: otpPhone }) })
      setMessage(data.placeholder_code ? `OTP sent. Local placeholder code: ${data.placeholder_code}` : 'OTP sent by SMS.')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const verifyOtp = async () => {
    resetAlerts()
    setLoading(true)
    try {
      const data = await api('/auth/verify-otp', { method: 'POST', body: JSON.stringify({ phone: otpPhone, code: otpCode }) })
      setToken(data.token)
      setCurrentUser(data.user)
      localStorage.setItem('agri_token', data.token)
      localStorage.setItem('agri_user', JSON.stringify(data.user))
      setMessage(`Signed in as ${data.user.name}`)
      setView('market')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const signOut = async () => {
    try { if (token) { await api('/auth/logout', { method: 'POST', headers: authHeaders }) } } catch (err) {}
    setToken('')
    setCurrentUser(null)
    setOrders([])
    setVerificationRequests([])
    setAuditLogs([])
    localStorage.removeItem('agri_token')
    localStorage.removeItem('agri_user')
    setMessage('Signed out. Public browsing is still available.')
    setView('market')
  }

  const uploadImage = async (file) => {
    if (!file || !token) return null
    const formData = new FormData()
    formData.append('image', file)
    return api('/images/upload', { method: 'POST', body: formData, headers: authHeaders })
  }

  // Marketplace actions
  const createListing = async (e) => {
    e.preventDefault()
    if (!currentUser) {
      jumpToAuth('Farmers can browse without an account, but posting harvest requires a farmer profile.')
      return
    }
    if (!isFarmer) {
      setError('Only farmer profiles can post harvest listings.')
      return
    }
    resetAlerts()
    setLoading(true)
    try {
      const fileInput = document.getElementById('listing-upload')
      let imageUrls = [...listingForm.image_urls]
      if (fileInput?.files?.[0]) {
        const uploaded = await uploadImage(fileInput.files[0])
        const abs = uploaded.image_url.startsWith('http')
          ? uploaded.image_url
          : `${API_BASE}${uploaded.image_url}`
        imageUrls = [...imageUrls, abs]
      }
      await api('/listings', { method: 'POST', body: JSON.stringify({ ...listingForm, image_urls: imageUrls }), headers: authHeaders })
      setListingForm(emptyListing)
      if (fileInput) fileInput.value = ''
      setMessage('Listing created')
      await loadPublicData()
      setView('market')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const placeOrder = async (e) => {
    e.preventDefault()
    if (!currentUser) {
      jumpToAuth('Buyers can browse without an account, but placing an order requires a buyer profile.')
      return
    }
    if (!isBuyer) {
      setError('Only buyer profiles can place orders.')
      return
    }
    resetAlerts()
    setLoading(true)
    try {
      await api('/orders', { method: 'POST', body: JSON.stringify({ ...orderForm, listing_id: Number(orderForm.listing_id) }), headers: authHeaders })
      setOrderForm(emptyOrder)
      setMessage('Order placed. Farmer was notified by SMS or placeholder log.')
      await loadPrivateData()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const updateOrder = async (orderId, status) => {
    resetAlerts()
    setLoading(true)
    try {
      await api(`/orders/${orderId}`, { method: 'PATCH', body: JSON.stringify({ status }), headers: authHeaders })
      setMessage(`Order ${status}`)
      await loadPrivateData()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const addReview = async (e) => {
    e.preventDefault()
    if (!currentUser) {
      jumpToAuth('Only signed-in buyers can leave reviews after a transaction.')
      return
    }
    if (!isBuyer) {
      setError('Only buyer profiles can submit reviews.')
      return
    }
    resetAlerts()
    setLoading(true)
    try {
      await api('/reviews', { method: 'POST', body: JSON.stringify({ ...reviewForm, farmer_id: Number(reviewForm.farmer_id), order_id: reviewForm.order_id ? Number(reviewForm.order_id) : undefined, score: Number(reviewForm.score) }), headers: authHeaders })
      setReviewForm(emptyReview)
      setMessage('Review submitted')
      await loadPublicData()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Trust, support, and admin workflows
  const requestVerification = async () => {
    resetAlerts()
    setLoading(true)
    try {
      await api('/verification/request', { method: 'POST', body: JSON.stringify({ document_type: 'national_id', document_reference: `placeholder-review:${currentUser.phone}` }), headers: authHeaders })
      setMessage('Verification request submitted for manual review.')
      await loadPrivateData()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }


  const createSupportTicket = async (e) => {
    e.preventDefault()
    if (!currentUser) {
      jumpToAuth('Create a profile or sign in to contact support about disputes or verification issues.')
      return
    }
    resetAlerts()
    setLoading(true)
    try {
      await api('/support-tickets', { method: 'POST', body: JSON.stringify(supportForm), headers: authHeaders })
      setSupportForm(emptySupport)
      setMessage('Support ticket created')
      await loadPrivateData()
      setView('support')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const updateSupportTicket = async (ticketId, status) => {
    resetAlerts()
    setLoading(true)
    try {
      await api(`/admin/support-tickets/${ticketId}`, { method: 'PATCH', body: JSON.stringify({ status, admin_notes: supportNotes[ticketId] || '' }), headers: authHeaders })
      setMessage(`Support ticket ${status}`)
      await loadPrivateData()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const reviewVerificationRequest = async (requestId, status) => {
    resetAlerts()
    setLoading(true)
    try {
      await api(`/admin/verification-requests/${requestId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, review_notes: verificationNotes[requestId] || '' }),
        headers: authHeaders,
      })
      setMessage(`Verification request ${status}`)
      await loadPrivateData()
      await loadPublicData()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const startOrderFromListing = async (listing) => {
    if (!currentUser) {
      jumpToAuth('Create a buyer profile or sign in to place an order.')
      return
    }
    if (!isBuyer) {
      setError('Sign in with a buyer profile to place orders.')
      return
    }
    await recordInteraction('click', listing.id)
    setOrderForm({ listing_id: String(listing.id), quantity_requested: listing.quantity })
    setView('orders')
    setMessage(`Listing #${listing.id} added to your order form.`)
    await loadRecommendations()
  }

  const tabs = ['market', 'auth', 'post', 'orders', 'reviews', 'support', 'pilot']
  const location = useLocation()

  useEffect(() => {
    if (location.pathname === '/admin') {
      document.title = 'Soko Admin'
    } else {
      document.title = 'Soko — Agri Marketplace'
    }
  }, [location.pathname])

  const sitePage = (
    <div className="page-shell">
    <div className="page">
        <header className="hero">
          <div>
            <span className="eyebrow">Soko · Rwanda + East Africa</span>
            <h1>Soko</h1>
            <p className="hero-tagline">Agri Marketplace</p>
            <p>
              Anyone can browse harvest listings. Farmers and buying businesses must create a profile and sign in to
              post harvest, place orders, request verification, and leave reviews.
            </p>
          </div>
          <div className="auth-state">
            {currentUser ? (
              <>
                <div className="user-pill">
                  <strong>{currentUser.name}</strong>
                  <span>{currentUser.role}</span>
                  <span>{currentUser.location}</span>
                  {currentUser.is_verified ? <span>Verified</span> : <span>Unverified</span>}
                  {currentUser.is_admin ? <span>Admin</span> : null}
                </div>
                <button className="secondary" onClick={signOut}>Sign out</button>
              </>
            ) : (
              <div className="guest-pill">
                <span className="small">Browsing as guest</span>
                <button className="secondary" onClick={() => jumpToAuth()}>Create profile / Sign in</button>
              </div>
            )}
          </div>
        </header>

        <nav className="nav">
          {tabs.map((item) => (
            <button key={item} className={view === item ? 'active' : 'secondary'} onClick={() => setView(item)}>{item}</button>
          ))}
        </nav>
        {currentUser?.is_admin && (
          <div className="nav-aux">
            <Link to="/admin" className="button-link">Soko Admin</Link>
            <p className="nav-aux-hint">Platform metrics, verification queue, audit log, and ticket moderation</p>
          </div>
        )}

        {message && <div className="message success">{message}</div>}
        {error && <div className="message error">{error}</div>}
        {loading && <div className="message info">Processing request…</div>}

        {view === 'market' && (
          <section className="stack">
            <section className="panel">
              <SectionTitle title="Marketplace" text="Browse freely. Sign in with a buyer profile to place an order, or a farmer profile to post harvest." />
              <div className="filters">
                <input placeholder="Search crop or farmer" value={search} onChange={(e) => setSearch(e.target.value)} />
                <input placeholder="Filter by location" value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)} />
                <button type="button" onClick={runSearch}>Search</button>
                <button type="button" className="secondary" onClick={() => { setSearch(''); setLocationFilter(''); loadPublicData() }}>Clear</button>
              </div>
            </section>

            <section className="panel">
              <SectionTitle title={currentUser ? "Recommended for you" : "Recommended listings"} text={currentUser ? "Level 1 rules use trust, location, and rating. Level 2 adds what you searched and viewed." : "These are ranked by trust, quality signals, and freshness."} />
              <div className="listing-grid">
                {recommendations.map((item) => (
                  <article className="card" key={`rec-${item.listing.id}`}>
                    <img src={item.listing.image_urls?.[0] || item.listing.image_url || 'https://images.unsplash.com/photo-1523741543316-beb7fc7023d8?auto=format&fit=crop&w=1200&q=80'} alt={item.listing.crop} />
                    <div className="card-body">
                      <div className="card-header">
                        <h3>{item.listing.crop}</h3>
                        <span className="badge inline">Score {item.score.toFixed(1)}</span>
                      </div>
                      <p className="small">{item.reason}</p>
                      <ul>
                        <li><strong>Farmer:</strong> {item.listing.farmer.name}</li>
                        <li><strong>Price:</strong> {item.listing.price}</li>
                        <li><strong>Location:</strong> {item.listing.location}</li>
                      </ul>
                      <div className="row wrap">
                        <button type="button" className="secondary" onClick={() => { recordInteraction('view', item.listing.id); setMessage(`Saved ${item.listing.crop} as a viewed listing.`) }}>Track view</button>
                        <button type="button" onClick={() => startOrderFromListing(item.listing)}>{currentUser ? 'Use in order form' : 'Sign in to order'}</button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <section className="panel">
              <SectionTitle title="All listings" text="Search results are ranked with basic marketplace rules: crop match, location, trust, rating, and freshness." />
              <div className="listing-grid">
                {filteredListings.map((listing) => (
                  <article className="card" key={listing.id}>
                    <img src={listing.image_urls?.[0] || listing.image_url || 'https://images.unsplash.com/photo-1523741543316-beb7fc7023d8?auto=format&fit=crop&w=1200&q=80'} alt={listing.crop} />
                    <div className="card-body">
                      <div className="card-header">
                        <h3>{listing.crop}</h3>
                        <span className="badge">{listing.farmer.is_verified ? 'Verified farmer' : 'Pending verification'}</span>
                      </div>
                      <p>{listing.description || 'No description yet.'}</p>
                      <ul>
                        <li><strong>Farmer:</strong> {listing.farmer.name}</li>
                        <li><strong>Phone:</strong> {listing.farmer.phone}</li>
                        <li><strong>Quantity:</strong> {listing.quantity}</li>
                        <li><strong>Price:</strong> {listing.price}</li>
                        <li><strong>Location:</strong> {listing.location}</li>
                      </ul>
                      <div className="row wrap">
                        <button type="button" className="secondary" onClick={() => { recordInteraction('view', listing.id); setMessage(`Viewed ${listing.crop}. Recommendations will improve.`) }}>View listing</button>
                        <button type="button" onClick={() => { recordInteraction('click', listing.id); startOrderFromListing(listing) }}>{currentUser ? 'Use in order form' : 'Sign in to order'}</button>
                        {!currentUser && <button type="button" className="secondary" onClick={() => jumpToAuth('Create a buyer or farmer profile to take action on listings.')}>Create profile</button>}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </section>
        )}

        {view === 'auth' && (
          <section className="two-col">
            <form className="panel" onSubmit={handleRegister}>
              <SectionTitle title="Create profile" text="Farmers and buying businesses must create a profile before they can post harvest or place an order." />
              <input required placeholder="Full name or business contact" value={registerForm.name} onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })} />
              <input required placeholder="Phone number" value={registerForm.phone} onChange={(e) => setRegisterForm({ ...registerForm, phone: e.target.value })} />
              <select value={registerForm.role} onChange={(e) => setRegisterForm({ ...registerForm, role: e.target.value })}>
                <option value="farmer">Farmer</option>
                <option value="buyer">Buyer / business</option>
              </select>
              <input required placeholder="Location" value={registerForm.location} onChange={(e) => setRegisterForm({ ...registerForm, location: e.target.value })} />
              <button type="submit">Create profile</button>
            </form>

            <div className="panel">
              <SectionTitle title="Phone OTP sign-in" text="Production uses real OTP by SMS. Local development returns a placeholder code." />
              <input placeholder="Phone number" value={otpPhone} onChange={(e) => setOtpPhone(e.target.value)} />
              <div className="row">
                <button type="button" onClick={requestOtp}>Request OTP</button>
                <button type="button" className="secondary" onClick={verifyOtp}>Verify OTP</button>
              </div>
              <input placeholder="OTP code" value={otpCode} onChange={(e) => setOtpCode(e.target.value)} />
              {currentUser && currentUser.role === 'farmer' && !currentUser.is_verified && (
                <button type="button" onClick={requestVerification}>Request farmer verification</button>
              )}
            </div>
          </section>
        )}

        {view === 'post' && (
          !currentUser ? (
            <section className="panel">
              <SectionTitle title="Post harvest" text="Guests can browse, but only signed-in farmers can publish listings." />
              <GateNotice
                title="Farmer profile required"
                text="Create a farmer profile and sign in with your phone number to post harvest and manage incoming orders."
                actionText="Create profile / Sign in"
                onAction={() => jumpToAuth('Create a farmer profile to post harvest.')}
              />
            </section>
          ) : !isFarmer ? (
            <section className="panel">
              <SectionTitle title="Post harvest" text="This action is restricted to farmer accounts." />
              <GateNotice
                title="Wrong profile type"
                text="You are signed in as a buyer. Sign in with a farmer profile to publish harvest listings."
                actionText="Go to sign in"
                onAction={() => setView('auth')}
              />
            </section>
          ) : (
            <form className="panel" onSubmit={createListing}>
              <SectionTitle title="Create listing" text="Farmers can upload one pilot image and publish a listing." />
              <div className="two-col-grid">
                <input required placeholder="Crop" value={listingForm.crop} onChange={(e) => setListingForm({ ...listingForm, crop: e.target.value })} />
                <input required placeholder="Quantity" value={listingForm.quantity} onChange={(e) => setListingForm({ ...listingForm, quantity: e.target.value })} />
                <input required placeholder="Price" value={listingForm.price} onChange={(e) => setListingForm({ ...listingForm, price: e.target.value })} />
                <input required placeholder="Location" value={listingForm.location} onChange={(e) => setListingForm({ ...listingForm, location: e.target.value })} />
                <input placeholder="External image URL (optional)" value={listingForm.image_url} onChange={(e) => setListingForm({ ...listingForm, image_url: e.target.value })} />
                <input id="listing-upload" type="file" accept="image/png,image/jpeg,image/webp" />
              </div>
              <textarea placeholder="Description" value={listingForm.description} onChange={(e) => setListingForm({ ...listingForm, description: e.target.value })} />
              <button type="submit">Publish listing</button>
            </form>
          )
        )}

        {view === 'orders' && (
          !currentUser ? (
            <section className="panel">
              <SectionTitle title="Orders" text="Guests can browse the market, but placing orders requires a buyer profile." />
              <GateNotice
                title="Buyer profile required"
                text="Create a buyer or business profile and sign in with phone OTP before you place orders with farmers."
                actionText="Create profile / Sign in"
                onAction={() => jumpToAuth('Create a buyer profile to place orders.')}
              />
            </section>
          ) : !isBuyer && !isFarmer ? null : (
            <section className="two-col">
              <form className="panel" onSubmit={placeOrder}>
                <SectionTitle title="Place order" text="Buyers can request a quantity from a selected listing. Farmers can view and manage order status." />
                {isBuyer ? (
                  <>
                    <input required placeholder="Listing ID" value={orderForm.listing_id} onChange={(e) => setOrderForm({ ...orderForm, listing_id: e.target.value })} />
                    <input required placeholder="Quantity requested" value={orderForm.quantity_requested} onChange={(e) => setOrderForm({ ...orderForm, quantity_requested: e.target.value })} />
                    <button type="submit">Submit order</button>
                    <p className="small">Only buyer profiles can create orders.</p>
                  </>
                ) : (
                  <GateNotice
                    title="Buyer action only"
                    text="You are signed in as a farmer. Farmers can manage incoming orders on the right, but they cannot place new orders."
                    actionText="Browse market"
                    onAction={() => setView('market')}
                  />
                )}
              </form>

              <div className="panel">
                <SectionTitle title={isBuyer ? 'My orders' : 'Incoming orders'} text="Order updates are visible here for buyers and farmers." />
                <div className="stack">
                  {orders.map((order) => (
                    <div className="order-card" key={order.id}>
                      <div><strong>Order #{order.id}</strong></div>
                      <div>Listing: {order.listing_id}</div>
                      <div>Quantity: {order.quantity_requested}</div>
                      <div>Status: <span className="badge inline">{order.status}</span></div>
                      {isFarmer && (
                        <div className="row wrap">
                          {['accepted', 'rejected', 'completed'].map((status) => (
                            <button key={status} className="secondary" type="button" onClick={() => updateOrder(order.id, status)}>{status}</button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  {!orders.length && <p className="small">No orders yet for this profile.</p>}
                </div>
              </div>
            </section>
          )
        )}

        {view === 'reviews' && (
          <section className="two-col">
            <form className="panel" onSubmit={addReview}>
              <SectionTitle title="Add review" text="Only signed-in buyers can leave transaction feedback for farmers." />
              {!isBuyer && (
                <p className="small">Browse reviews freely. Sign in with a buyer profile to submit a new review.</p>
              )}
              <input required placeholder="Farmer ID" value={reviewForm.farmer_id} onChange={(e) => setReviewForm({ ...reviewForm, farmer_id: e.target.value })} disabled={!isBuyer} />
              <input placeholder="Completed order ID (recommended)" value={reviewForm.order_id} onChange={(e) => setReviewForm({ ...reviewForm, order_id: e.target.value })} disabled={!isBuyer} />
              <input required placeholder="Buyer name" value={reviewForm.buyer_name} onChange={(e) => setReviewForm({ ...reviewForm, buyer_name: e.target.value })} disabled={!isBuyer} />
              <input required type="number" min="1" max="5" step="0.5" placeholder="Score" value={reviewForm.score} onChange={(e) => setReviewForm({ ...reviewForm, score: e.target.value })} disabled={!isBuyer} />
              <textarea required placeholder="Feedback" value={reviewForm.text} onChange={(e) => setReviewForm({ ...reviewForm, text: e.target.value })} disabled={!isBuyer} />
              <button type="submit" disabled={!isBuyer}>Submit review</button>
            </form>

            <div className="panel">
              <SectionTitle title="Recent reviews" text="Public trust signals stay visible even for guest users." />
              <div className="stack">
                {reviews.map((review) => (
                  <div className="review-card" key={review.id}>
                    <div><strong>Farmer #{review.farmer_id}</strong></div>
                    <div>Buyer: {review.buyer_name}</div>
                    <div>Score: {review.score}</div>
                    <p>{review.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}


        {view === 'support' && (
          <section className="two-col">
            <form className="panel" onSubmit={createSupportTicket}>
              <SectionTitle title="Support and disputes" text="Use support tickets for disputes, abuse reports, verification help, or general issues." />
              <select value={supportForm.category} onChange={(e) => setSupportForm({ ...supportForm, category: e.target.value })} disabled={!currentUser}>
                <option value="general">General</option>
                <option value="dispute">Dispute</option>
                <option value="abuse">Abuse</option>
                <option value="bug">Bug</option>
              </select>
              <input required placeholder="Subject" value={supportForm.subject} onChange={(e) => setSupportForm({ ...supportForm, subject: e.target.value })} disabled={!currentUser} />
              <textarea required placeholder="Describe the issue" value={supportForm.message} onChange={(e) => setSupportForm({ ...supportForm, message: e.target.value })} disabled={!currentUser} />
              <button type="submit" disabled={!currentUser}>Create support ticket</button>
              {!currentUser && <p className="small">Sign in to create support tickets and receive help.</p>}
            </form>

            <div className="panel">
              <SectionTitle title="My support tickets" text="Admins see all tickets. Other users see their own." />
              <div className="stack">
                {supportTickets.map((ticket) => (
                  <div className="review-card" key={ticket.id}>
                    <div><strong>Ticket #{ticket.id}</strong></div>
                    <div>Category: {ticket.category}</div>
                    <div>Status: {ticket.status}</div>
                    <div>{ticket.subject}</div>
                    <p>{ticket.message}</p>
                    {currentUser?.is_admin && (
                      <p className="small">
                        <Link to="/admin">Soko Admin</Link> — update status and notes for all tickets
                      </p>
                    )}
                  </div>
                ))}
                {!supportTickets.length && <p className="small">No support tickets yet.</p>}
              </div>
            </div>
          </section>
        )}

        {view === 'pilot' && (
          <section className="panel">
            <SectionTitle title="Pilot operating model" text="This is the intended usage model for real pilot users." />
            <div className="stack">
              <div className="review-card">
                <strong>Public browsing</strong>
                <p>Any visitor can search listings, compare prices, and see trust signals before signing in.</p>
              </div>
              <div className="review-card">
                <strong>Farmer accounts</strong>
                <p>Farmers create a phone-based profile, sign in with OTP, post harvest, and request verification.</p>
              </div>
              <div className="review-card">
                <strong>Buyer or business accounts</strong>
                <p>Wholesalers, restaurants, and other buyers create a phone-based profile before placing orders and leaving reviews.</p>
              </div>
              <div className="review-card">
                <strong>Manual verification</strong>
                <p>Admins review placeholder documents or external evidence before issuing verified badges.</p>
              </div>
            </div>
          </section>
        )}

      </div>
    </div>
  )

  const adminPage = (
    <div className="page-shell">
      <div className="page">
        <header className="hero hero-admin">
          <div>
            <span className="eyebrow">Soko</span>
            <h1>Soko Admin</h1>
            <p>Platform tools for operations — not shown to public marketplace visitors.</p>
          </div>
          <div className="auth-state">
            {currentUser && (
              <div className="user-pill">
                <strong>{currentUser.name}</strong>
                <span>admin</span>
              </div>
            )}
            <Link to="/" className="back-to-site">← Back to website</Link>
            <button type="button" className="secondary" onClick={signOut}>
              Sign out
            </button>
          </div>
        </header>

        {message && <div className="message success">{message}</div>}
        {error && <div className="message error">{error}</div>}
        {loading && <div className="message info">Processing request…</div>}

        <section className="admin-page-grid">
          <div className="admin-grid">
            <div className="panel">
              <SectionTitle title="Platform summary" text="Quick production-style admin metrics." />
              {metrics && (
                <div className="stack">
                  <div className="review-card">
                    <div>Users: {metrics.users}</div>
                    <div>Listings: {metrics.listings}</div>
                    <div>Orders: {metrics.orders}</div>
                    <div>Reviews: {metrics.reviews}</div>
                    <div>Verification requests: {metrics.verification_requests}</div>
                    <div>Support tickets: {metrics.support_tickets}</div>
                  </div>
                </div>
              )}
            </div>
            <div className="panel">
              <SectionTitle title="Verification requests" text="Admin review queue for farmer and buyer verification." />
              <div className="stack">
                {verificationRequests.map((item) => (
                  <div className="review-card" key={item.id}>
                    <div>
                      <strong>Request #{item.id}</strong>
                    </div>
                    <div>User #{item.user_id}</div>
                    <div>{item.document_type}</div>
                    <div>{item.document_reference}</div>
                    <div>Status: {item.status}</div>
                    <textarea
                      placeholder="Review notes"
                      value={verificationNotes[item.id] || ''}
                      onChange={(e) => setVerificationNotes({ ...verificationNotes, [item.id]: e.target.value })}
                    />
                    <div className="row wrap">
                      <button type="button" onClick={() => reviewVerificationRequest(item.id, 'approved')}>
                        Approve
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => reviewVerificationRequest(item.id, 'rejected')}
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
                {!verificationRequests.length && <p className="small">No pending verification requests.</p>}
              </div>
            </div>

            <div className="panel">
              <SectionTitle title="Audit log" text="Production readiness includes visibility into key actions." />
              <div className="stack log-stack">
                {auditLogs.map((log) => (
                  <div className="review-card" key={log.id}>
                    <div>
                      <strong>{log.action}</strong>
                    </div>
                    <div>
                      {log.entity_type} #{log.entity_id}
                    </div>
                    <div>{log.details}</div>
                    <div className="small">{new Date(log.created_at).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="panel">
            <SectionTitle title="Support tickets (all)" text="Update status and internal notes for every ticket in the system." />
            <div className="stack">
              {supportTickets.map((ticket) => (
                <div className="review-card" key={ticket.id}>
                  <div>
                    <strong>Ticket #{ticket.id}</strong>
                  </div>
                  <div>Category: {ticket.category}</div>
                  <div>Status: {ticket.status}</div>
                  <div>{ticket.subject}</div>
                  <p>{ticket.message}</p>
                  <textarea
                    placeholder="Admin notes"
                    value={supportNotes[ticket.id] || ''}
                    onChange={(e) => setSupportNotes({ ...supportNotes, [ticket.id]: e.target.value })}
                  />
                  <div className="row wrap">
                    {['in_progress', 'resolved', 'closed'].map((status) => (
                      <button
                        key={status}
                        type="button"
                        className="secondary"
                        onClick={() => updateSupportTicket(ticket.id, status)}
                      >
                        {status}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
              {!supportTickets.length && <p className="small">No support tickets yet.</p>}
            </div>
          </div>
        </section>
      </div>
    </div>
  )

  return (
    <Routes>
      <Route path="/" element={sitePage} />
      <Route
        path="/admin"
        element={currentUser?.is_admin ? adminPage : <Navigate to="/" replace />}
      />
    </Routes>
  )
}
