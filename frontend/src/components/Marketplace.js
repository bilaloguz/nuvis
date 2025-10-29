import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useAuth } from '../contexts/AuthContext';

const Marketplace = () => {
  const { user: currentUser } = useAuth();
  const [scripts, setScripts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    page: 1,
    size: 20,
    total: 0
  });
  const [filters, setFilters] = useState({
    search: '',
    category: '',
    script_type: '',
    tags: '',
    sort_by: 'created_at',
    sort_order: 'desc',
    verified_only: false,
    min_rating: '',
    min_downloads: ''
  });
  const [categories, setCategories] = useState([]);
  const [tags, setTags] = useState([]);
  const [selectedScript, setSelectedScript] = useState(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importName, setImportName] = useState('');
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [scriptReviews, setScriptReviews] = useState([]);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewForm, setReviewForm] = useState({
    rating: 5,
    review_text: ''
  });
  const [userReview, setUserReview] = useState(null);
  const [searchSuggestions, setSearchSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchHistory, setSearchHistory] = useState([]);
  const [filtersExpanded, setFiltersExpanded] = useState(false);

  useEffect(() => {
    fetchScripts();
    fetchCategories();
    fetchTags();
    // Load search history from localStorage
    const savedHistory = localStorage.getItem('marketplace_search_history');
    if (savedHistory) {
      setSearchHistory(JSON.parse(savedHistory));
    }
  }, [pagination.page, pagination.size, filters]);

  const fetchScripts = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.set('page', String(pagination.page));
      params.set('size', String(pagination.size));

      // Append only non-empty filters
      if (filters.search && filters.search.trim()) params.set('search', filters.search.trim());
      if (filters.category) params.set('category', filters.category);
      if (filters.script_type) params.set('script_type', filters.script_type);
      if (filters.tags && filters.tags.trim()) params.set('tags', filters.tags.trim());
      if (filters.sort_by) params.set('sort_by', filters.sort_by);
      if (filters.sort_order) params.set('sort_order', filters.sort_order);
      if (filters.verified_only) params.set('verified_only', 'true');
      if (filters.min_rating) params.set('min_rating', String(filters.min_rating));
      if (filters.min_downloads) params.set('min_downloads', String(filters.min_downloads));
      
      const response = await axios.get(`/api/marketplace/scripts?${params.toString()}`);
      setScripts(response.data.scripts);
      setPagination(prev => ({
        ...prev,
        total: response.data.total,
        page: response.data.page,
        size: response.data.size
      }));
    } catch (error) {
      console.error('Error fetching marketplace scripts:', error);
      toast.error('Failed to load marketplace scripts');
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await axios.get('/api/marketplace/categories');
      setCategories(response.data);
    } catch (error) {
      console.error('Error fetching categories:', error);
    }
  };

  const fetchTags = async () => {
    try {
      const response = await axios.get('/api/marketplace/tags');
      setTags(response.data);
    } catch (error) {
      console.error('Error fetching tags:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPagination(prev => ({ ...prev, page: 1 })); // Reset to first page
    
    // Save search to history
    if (key === 'search' && value.trim()) {
      const newHistory = [value.trim(), ...searchHistory.filter(item => item !== value.trim())].slice(0, 10);
      setSearchHistory(newHistory);
      localStorage.setItem('marketplace_search_history', JSON.stringify(newHistory));
    }
  };

  const handleSearchInput = (value) => {
    setFilters(prev => ({ ...prev, search: value }));
    setShowSuggestions(value.length > 0);
    
    // Generate suggestions based on categories, tags, and search history
    const suggestions = [];
    
    // Add matching categories
    categories.forEach(cat => {
      if (cat.toLowerCase().includes(value.toLowerCase())) {
        suggestions.push({ type: 'category', value: cat, label: `Category: ${cat}` });
      }
    });
    
    // Add matching tags
    tags.forEach(tag => {
      if (tag.toLowerCase().includes(value.toLowerCase())) {
        suggestions.push({ type: 'tag', value: tag, label: `Tag: ${tag}` });
      }
    });
    
    // Add matching search history
    searchHistory.forEach(term => {
      if (term.toLowerCase().includes(value.toLowerCase()) && term !== value) {
        suggestions.push({ type: 'history', value: term, label: term });
      }
    });
    
    setSearchSuggestions(suggestions.slice(0, 8));
  };

  const handleSuggestionClick = (suggestion) => {
    if (suggestion.type === 'category') {
      setFilters(prev => ({ ...prev, search: '', category: suggestion.value }));
    } else if (suggestion.type === 'tag') {
      setFilters(prev => ({ ...prev, search: '', tags: suggestion.value }));
    } else {
      setFilters(prev => ({ ...prev, search: suggestion.value }));
    }
    setShowSuggestions(false);
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const clearSearchHistory = () => {
    setSearchHistory([]);
    localStorage.removeItem('marketplace_search_history');
  };

  const hasActiveFilters = () => {
    return filters.search || filters.category || filters.script_type || filters.tags || 
           filters.min_rating || filters.min_downloads || filters.verified_only;
  };

  const getActiveFiltersCount = () => {
    let count = 0;
    if (filters.search) count++;
    if (filters.category) count++;
    if (filters.script_type) count++;
    if (filters.tags) count++;
    if (filters.min_rating) count++;
    if (filters.min_downloads) count++;
    if (filters.verified_only) count++;
    return count;
  };

  const handlePageChange = (newPage) => {
    setPagination(prev => ({ ...prev, page: newPage }));
  };

  const handlePageSizeChange = (newSize) => {
    setPagination(prev => ({ ...prev, size: newSize, page: 1 }));
  };

  const handleImportScript = async () => {
    if (!selectedScript) return;

    try {
      const response = await axios.post('/api/marketplace/import', {
        marketplace_script_id: selectedScript.id,
        new_name: importName || selectedScript.name
      });

      toast.success('Script imported successfully!');
      setShowImportModal(false);
      setSelectedScript(null);
      setImportName('');
    } catch (error) {
      console.error('Error importing script:', error);
      toast.error(error.response?.data?.detail || 'Failed to import script');
    }
  };

  const handleDownloadScript = async (scriptId) => {
    try {
      await axios.post(`/api/marketplace/scripts/${scriptId}/download`);
      toast.success('Download recorded!');
    } catch (error) {
      console.error('Error recording download:', error);
    }
  };

  const fetchScriptReviews = async (scriptId) => {
    try {
      const response = await axios.get(`/api/marketplace/scripts/${scriptId}/reviews`);
      setScriptReviews(response.data.reviews);
    } catch (error) {
      console.error('Error fetching reviews:', error);
    }
  };

  const handleShowDetails = async (script) => {
    setSelectedScript(script);
    setShowDetailsModal(true);
    await fetchScriptReviews(script.id);
    // Check if user has already reviewed this script
    try {
      const response = await axios.get(`/api/marketplace/scripts/${script.id}/reviews`);
      const userReview = response.data.reviews.find(review => review.user_id === currentUser?.id);
      setUserReview(userReview || null);
    } catch (error) {
      console.error('Error checking user review:', error);
    }
  };

  const handleSubmitReview = async () => {
    if (!selectedScript) return;

    try {
      await axios.post(`/api/marketplace/scripts/${selectedScript.id}/reviews`, reviewForm);
      toast.success('Review submitted successfully!');
      setShowReviewModal(false);
      setReviewForm({ rating: 5, review_text: '' });
      // Refresh reviews and script data
      await fetchScriptReviews(selectedScript.id);
      await fetchScripts(); // Refresh to update rating averages
    } catch (error) {
      console.error('Error submitting review:', error);
      toast.error(error.response?.data?.detail || 'Failed to submit review');
    }
  };

  const handleEditReview = () => {
    if (userReview) {
      setReviewForm({
        rating: userReview.rating,
        review_text: userReview.review_text || ''
      });
      setShowReviewModal(true);
    }
  };

  const renderStars = (rating) => {
    const stars = [];
    const fullStars = Math.floor(rating);
    const hasHalfStar = rating % 1 !== 0;

    for (let i = 0; i < fullStars; i++) {
      stars.push(<i key={i} className="bi bi-star-fill text-warning"></i>);
    }

    if (hasHalfStar) {
      stars.push(<i key="half" className="bi bi-star-half text-warning"></i>);
    }

    const emptyStars = 5 - Math.ceil(rating);
    for (let i = 0; i < emptyStars; i++) {
      stars.push(<i key={`empty-${i}`} className="bi bi-star"></i>);
    }

    return stars;
  };

  const renderTags = (tagsString) => {
    if (!tagsString) return null;
    
    try {
      const tagList = JSON.parse(tagsString);
      return tagList.map((tag, index) => (
        <span key={index} className="badge bg-secondary me-1 mb-1">
          {tag}
        </span>
      ));
    } catch {
      return <span className="badge bg-secondary me-1 mb-1">{tagsString}</span>;
    }
  };

  const highlightSearchTerm = (text, searchTerm) => {
    if (!searchTerm || !text) return text;
    
    const regex = new RegExp(`(${searchTerm})`, 'gi');
    const parts = text.split(regex);
    
    return parts.map((part, index) => 
      regex.test(part) ? (
        <mark key={index} className="bg-warning text-dark">{part}</mark>
      ) : part
    );
  };

  const getSearchMatchCount = (script) => {
    if (!filters.search) return 0;
    
    const searchTerm = filters.search.toLowerCase();
    let matches = 0;
    
    if (script.name.toLowerCase().includes(searchTerm)) matches++;
    if (script.description && script.description.toLowerCase().includes(searchTerm)) matches++;
    if (script.content && script.content.toLowerCase().includes(searchTerm)) matches++;
    if (script.category && script.category.toLowerCase().includes(searchTerm)) matches++;
    if (script.tags && script.tags.toLowerCase().includes(searchTerm)) matches++;
    
    return matches;
  };

  return (
    <div className="container-fluid">
      <div className="row">
        <div className="col-12">
          <div className="d-flex justify-content-between align-items-center mb-4">
            <h2><i className="bi bi-shop me-2"></i>Script Marketplace</h2>
            <div className="d-flex gap-2">
              <button 
                className="btn btn-outline-primary"
                onClick={() => window.location.href = '/scripts'}
              >
                <i className="bi bi-arrow-left me-1"></i>Back to My Scripts
              </button>
            </div>
          </div>

          {/* Filters */}
          <div className="card shadow-lg mb-4">
            <div className="card-header">
              <div className="d-flex justify-content-between align-items-center mb-3">
                <h6 className="mb-0">
                  <i className="bi bi-funnel me-2"></i>Filters
                  {hasActiveFilters() && (
                    <span className="badge bg-primary ms-2">
                      {getActiveFiltersCount()} active
                    </span>
                  )}
                </h6>
                <div className="d-flex gap-2">
                  {hasActiveFilters() && (
                    <button
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => {
                        setFilters({
                          search: '',
                          category: '',
                          script_type: '',
                          tags: '',
                          sort_by: 'created_at',
                          sort_order: 'desc',
                          verified_only: false,
                          min_rating: '',
                          min_downloads: ''
                        });
                        setPagination(prev => ({ ...prev, page: 1 }));
                      }}
                    >
                      <i className="bi bi-x-circle me-1"></i>Clear All
                    </button>
                  )}
                  <button
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => setFiltersExpanded(!filtersExpanded)}
                  >
                    <i className={`bi ${filtersExpanded ? 'bi-chevron-up' : 'bi-chevron-down'} me-1`}></i>
                    {filtersExpanded ? 'Collapse' : 'Expand'} Filters
                  </button>
                </div>
              </div>
              
              {/* Search - Always Visible */}
              <div className="row g-3">
                <div className="col-12">
                  <label className="form-label">Search</label>
                  <div className="position-relative">
                    <input
                      type="text"
                      className="form-control border border-secondary"
                      placeholder="Search scripts, categories, tags..."
                      value={filters.search}
                      onChange={(e) => handleSearchInput(e.target.value)}
                      onFocus={() => setShowSuggestions(filters.search.length > 0)}
                      onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
                    />
                    {filters.search && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-secondary position-absolute end-0 top-50 translate-middle-y me-2"
                        onClick={() => {
                          setFilters(prev => ({ ...prev, search: '' }));
                          setShowSuggestions(false);
                        }}
                        style={{zIndex: 10}}
                      >
                        <i className="bi bi-x"></i>
                      </button>
                    )}
                    
                    {/* Search Suggestions Dropdown */}
                    {showSuggestions && (searchSuggestions.length > 0 || searchHistory.length > 0) && (
                      <div className="position-absolute w-100 bg-white border border-secondary rounded-bottom shadow-sm" style={{zIndex: 1000, top: '100%'}}>
                        {searchSuggestions.length > 0 ? (
                          <>
                            {searchSuggestions.map((suggestion, index) => (
                              <button
                                key={index}
                                type="button"
                                className="btn btn-link text-start w-100 text-decoration-none p-2 border-0"
                                onClick={() => handleSuggestionClick(suggestion)}
                              >
                                <i className={`bi ${suggestion.type === 'category' ? 'bi-tags' : suggestion.type === 'tag' ? 'bi-hash' : 'bi-clock-history'} me-2`}></i>
                                {suggestion.label}
                              </button>
                            ))}
                          </>
                        ) : (
                          <>
                            <div className="p-2 text-muted small">Recent searches:</div>
                            {searchHistory.slice(0, 5).map((term, index) => (
                              <button
                                key={index}
                                type="button"
                                className="btn btn-link text-start w-100 text-decoration-none p-2 border-0"
                                onClick={() => handleSuggestionClick({type: 'history', value: term, label: term})}
                              >
                                <i className="bi bi-clock-history me-2"></i>
                                {term}
                              </button>
                            ))}
                            <div className="border-top p-2">
                              <button
                                type="button"
                                className="btn btn-sm btn-outline-secondary"
                                onClick={clearSearchHistory}
                              >
                                <i className="bi bi-trash me-1"></i>Clear History
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
              
              {/* All Other Filters - Collapsible */}
              {filtersExpanded && (
                <>
                  <hr className="my-3" />
                  <div className="row g-3">
                    <div className="col-md-3">
                      <label className="form-label">Category</label>
                      <select
                        className="form-select border border-secondary"
                        value={filters.category}
                        onChange={(e) => handleFilterChange('category', e.target.value)}
                      >
                        <option value="">All Categories</option>
                        {categories.map(cat => (
                          <option key={cat} value={cat}>{cat}</option>
                        ))}
                      </select>
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">Type</label>
                      <select
                        className="form-select border border-secondary"
                        value={filters.script_type}
                        onChange={(e) => handleFilterChange('script_type', e.target.value)}
                      >
                        <option value="">All Types</option>
                        <option value="bash">Bash</option>
                        <option value="python">Python</option>
                        <option value="powershell">PowerShell</option>
                      </select>
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">Sort By</label>
                      <select
                        className="form-select border border-secondary"
                        value={filters.sort_by}
                        onChange={(e) => handleFilterChange('sort_by', e.target.value)}
                      >
                        <option value="created_at">Date Created</option>
                        <option value="updated_at">Date Updated</option>
                        <option value="download_count">Most Downloaded</option>
                        <option value="rating_average">Highest Rated</option>
                        <option value="rating_count">Most Reviewed</option>
                        <option value="name">Name (A-Z)</option>
                      </select>
                    </div>
                    <div className="col-md-3">
                      <label className="form-label">Order</label>
                      <select
                        className="form-select border border-secondary"
                        value={filters.sort_order}
                        onChange={(e) => handleFilterChange('sort_order', e.target.value)}
                      >
                        <option value="desc">Descending</option>
                        <option value="asc">Ascending</option>
                      </select>
                    </div>
                  </div>
                  
                  <div className="row g-3 mt-3">
                    <div className="col-md-4">
                      <label className="form-label">Min Rating</label>
                      <select
                        className="form-select border border-secondary"
                        value={filters.min_rating}
                        onChange={(e) => handleFilterChange('min_rating', e.target.value)}
                      >
                        <option value="">Any Rating</option>
                        <option value="1">1+ Stars</option>
                        <option value="2">2+ Stars</option>
                        <option value="3">3+ Stars</option>
                        <option value="4">4+ Stars</option>
                        <option value="5">5 Stars</option>
                      </select>
                    </div>
                    <div className="col-md-4">
                      <label className="form-label">Min Downloads</label>
                      <input
                        type="number"
                        className="form-control border border-secondary"
                        placeholder="0"
                        min="0"
                        value={filters.min_downloads}
                        onChange={(e) => handleFilterChange('min_downloads', e.target.value)}
                      />
                    </div>
                    <div className="col-md-4">
                      <label className="form-label">Tags</label>
                      <input
                        type="text"
                        className="form-control border border-secondary"
                        placeholder="tag1, tag2..."
                        value={filters.tags}
                        onChange={(e) => handleFilterChange('tags', e.target.value)}
                      />
                    </div>
                  </div>
                </>
              )}
              
              {/* Quick Filters Row - Always Visible */}
              <div className="row g-3 mt-3">
                <div className="col-12">
                  <label className="form-label">Quick Filters</label>
                  <div className="d-flex gap-2 flex-wrap">
                    <button
                      className={`btn btn-sm ${filters.sort_by === 'rating_average' && filters.sort_order === 'desc' ? 'btn-primary' : 'btn-outline-primary'}`}
                      onClick={() => {
                        setFilters(prev => ({ ...prev, sort_by: 'rating_average', sort_order: 'desc' }));
                        setPagination(prev => ({ ...prev, page: 1 }));
                      }}
                    >
                      <i className="bi bi-star-fill me-1"></i>Top Rated
                    </button>
                    <button
                      className={`btn btn-sm ${filters.sort_by === 'download_count' && filters.sort_order === 'desc' ? 'btn-primary' : 'btn-outline-primary'}`}
                      onClick={() => {
                        setFilters(prev => ({ ...prev, sort_by: 'download_count', sort_order: 'desc' }));
                        setPagination(prev => ({ ...prev, page: 1 }));
                      }}
                    >
                      <i className="bi bi-download me-1"></i>Most Downloaded
                    </button>
                    <button
                      className={`btn btn-sm ${filters.sort_by === 'created_at' && filters.sort_order === 'desc' ? 'btn-primary' : 'btn-outline-primary'}`}
                      onClick={() => {
                        setFilters(prev => ({ ...prev, sort_by: 'created_at', sort_order: 'desc' }));
                        setPagination(prev => ({ ...prev, page: 1 }));
                      }}
                    >
                      <i className="bi bi-clock me-1"></i>Newest
                    </button>
                    <button
                      className={`btn btn-sm ${filters.verified_only ? 'btn-primary' : 'btn-outline-primary'}`}
                      onClick={() => {
                        setFilters(prev => ({ ...prev, verified_only: !prev.verified_only }));
                        setPagination(prev => ({ ...prev, page: 1 }));
                      }}
                    >
                      <i className="bi bi-patch-check me-1"></i>Verified Only
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Search Results Summary */}
          {!loading && hasActiveFilters() && (
            <div className="alert alert-info mb-3">
              <div className="d-flex align-items-center">
                <i className="bi bi-search me-2"></i>
                <strong>Search Results:</strong> {pagination.total} script{pagination.total !== 1 ? 's' : ''} found
                {filters.search && (
                  <span className="ms-2">
                    for "<strong>{filters.search}</strong>"
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Scripts Grid */}
          {loading ? (
            <div className="text-center py-5">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            </div>
          ) : scripts.length === 0 ? (
            <div className="text-center py-5">
              <i className="bi bi-search display-1 text-muted"></i>
              <h4 className="mt-3">No scripts found</h4>
              <p className="text-muted">
                {hasActiveFilters()
                  ? "Try adjusting your search criteria or filters."
                  : "No scripts are available in the marketplace yet."
                }
              </p>
              {hasActiveFilters() && (
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    setFilters({
                      search: '',
                      category: '',
                      script_type: '',
                      tags: '',
                      sort_by: 'created_at',
                      sort_order: 'desc',
                      verified_only: false,
                      min_rating: '',
                      min_downloads: ''
                    });
                    setPagination(prev => ({ ...prev, page: 1 }));
                  }}
                >
                  <i className="bi bi-arrow-clockwise me-1"></i>Clear All Filters
                </button>
              )}
            </div>
          ) : (
            <div className="row">
              {scripts.map(script => (
                <div key={script.id} className="col-md-6 col-lg-4 mb-4">
                  <div className="card h-100 shadow-sm">
                    <div className="card-header d-flex justify-content-between align-items-center">
                      <h6 className="mb-0">
                        {highlightSearchTerm(script.name, filters.search)}
                        {filters.search && getSearchMatchCount(script) > 0 && (
                          <span className="badge bg-info ms-2" title={`${getSearchMatchCount(script)} matches`}>
                            {getSearchMatchCount(script)}
                          </span>
                        )}
                      </h6>
                      {script.is_verified && (
                        <i className="bi bi-patch-check-fill text-success" title="Verified"></i>
                      )}
                    </div>
                    <div className="card-body">
                      <p className="card-text small" style={{minHeight:'3rem', fontWeight: 600}}>
                        {highlightSearchTerm(script.description || 'No description', filters.search)}
                      </p>
                      
                      <div className="mb-2">
                        <span className="badge bg-primary me-1 text-dark fw-bold">{script.script_type}</span>
                        {script.category && (
                          <span className="badge bg-info me-1 text-dark fw-bold">{script.category}</span>
                        )}
                      </div>

                      <div className="mb-2">
                        {renderTags(script.tags)}
                      </div>

                      <div className="d-flex justify-content-between align-items-center mb-2">
                        <div>
                          {renderStars(script.rating_average)}
                          <small className="ms-1" style={{color:'var(--text-secondary)'}}>
                            ({script.rating_count} reviews)
                          </small>
                        </div>
                        <small style={{color:'var(--text-secondary)'}}>
                          <i className="bi bi-download me-1"></i>
                          {script.download_count}
                        </small>
                      </div>

                      <div className="d-flex justify-content-between align-items-center">
                        <small className="text-muted">
                          by {script.author_username}
                        </small>
                        <small className="text-muted">
                          v{script.version}
                        </small>
                      </div>
                    </div>
                    <div className="card-footer">
                      <div className="d-flex gap-2">
                        <button
                          className="btn btn-outline-primary btn-sm"
                          onClick={() => handleShowDetails(script)}
                        >
                          <i className="bi bi-eye me-1"></i>Details
                        </button>
                        <button
                          className="btn btn-outline-success btn-sm flex-fill"
                          onClick={() => {
                            setSelectedScript(script);
                            setShowImportModal(true);
                          }}
                        >
                          <i className="bi bi-download me-1"></i>Import
                        </button>
                        <button
                          className="btn btn-outline-secondary btn-sm"
                          onClick={() => handleDownloadScript(script.id)}
                          title="Record Download"
                        >
                          <i className="bi bi-heart"></i>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {pagination.total > 0 && (
            <div className="d-flex justify-content-between align-items-center mt-4">
              <div>
                <select
                  className="form-select form-select-sm border border-secondary d-inline-block"
                  style={{width: '80px'}}
                  value={pagination.size}
                  onChange={(e) => handlePageSizeChange(parseInt(e.target.value))}
                >
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
                <span className="ms-2" style={{color:'var(--text-secondary)'}}>
                  Showing {((pagination.page - 1) * pagination.size) + 1} to {Math.min(pagination.page * pagination.size, pagination.total)} of {pagination.total} scripts
                </span>
              </div>
              
              <nav>
                <ul className="pagination pagination-sm mb-0">
                  <li className={`page-item ${pagination.page === 1 ? 'disabled' : ''}`}>
                    <button
                      className="page-link border border-secondary"
                      onClick={() => handlePageChange(pagination.page - 1)}
                      disabled={pagination.page === 1}
                    >
                      Previous
                    </button>
                  </li>
                  
                  {Array.from({ length: Math.ceil(pagination.total / pagination.size) }, (_, i) => i + 1)
                    .filter(page => 
                      page === 1 || 
                      page === Math.ceil(pagination.total / pagination.size) ||
                      Math.abs(page - pagination.page) <= 2
                    )
                    .map((page, index, array) => (
                      <React.Fragment key={page}>
                        {index > 0 && array[index - 1] !== page - 1 && (
                          <li className="page-item disabled">
                            <span className="page-link border border-secondary">...</span>
                          </li>
                        )}
                        <li className={`page-item ${pagination.page === page ? 'active' : ''}`}>
                          <button
                            className="page-link border border-secondary"
                            onClick={() => handlePageChange(page)}
                          >
                            {page}
                          </button>
                        </li>
                      </React.Fragment>
                    ))}
                  
                  <li className={`page-item ${pagination.page === Math.ceil(pagination.total / pagination.size) ? 'disabled' : ''}`}>
                    <button
                      className="page-link border border-secondary"
                      onClick={() => handlePageChange(pagination.page + 1)}
                      disabled={pagination.page === Math.ceil(pagination.total / pagination.size)}
                    >
                      Next
                    </button>
                  </li>
                </ul>
              </nav>
            </div>
          )}
        </div>
      </div>

      {/* Import Modal */}
      {showImportModal && selectedScript && (
        <div className="modal show d-block" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
          <div className="modal-dialog">
            <div className="modal-content">
              <div className="modal-header border-secondary">
                <h5 className="modal-title">Import Script</h5>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => {
                    setShowImportModal(false);
                    setSelectedScript(null);
                    setImportName('');
                  }}
                ></button>
              </div>
              <div className="modal-body">
                <p>Import <strong>{selectedScript.name}</strong> to your local scripts?</p>
                <div className="mb-3">
                  <label className="form-label">Script Name (optional)</label>
                  <input
                    type="text"
                    className="form-control border border-secondary"
                    value={importName}
                    onChange={(e) => setImportName(e.target.value)}
                    placeholder={selectedScript.name}
                  />
                  <div className="form-text" style={{color:'var(--text-secondary)'}}>
                    Leave empty to use the original name
                  </div>
                </div>
              </div>
              <div className="modal-footer border-secondary">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowImportModal(false);
                    setSelectedScript(null);
                    setImportName('');
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleImportScript}
                >
                  Import Script
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Script Details Modal */}
      {showDetailsModal && selectedScript && (
        <div className="modal show d-block" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
          <div className="modal-dialog modal-lg">
            <div className="modal-content">
              <div className="modal-header border-secondary">
                <h5 className="modal-title">
                  <i className="bi bi-file-code me-2"></i>
                  {selectedScript.name}
                  {selectedScript.is_verified && (
                    <i className="bi bi-patch-check-fill text-success ms-2" title="Verified"></i>
                  )}
                </h5>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => {
                    setShowDetailsModal(false);
                    setSelectedScript(null);
                    setScriptReviews([]);
                    setUserReview(null);
                  }}
                ></button>
              </div>
              <div className="modal-body">
                <div className="row">
                  <div className="col-md-8">
                    <div className="mb-3">
                      <h6>Description</h6>
                      <p className="text-muted">{selectedScript.description || 'No description provided'}</p>
                    </div>
                    
                    <div className="mb-3">
                      <h6>Script Content</h6>
                      <pre className="bg-light p-3 rounded" style={{maxHeight: '300px', overflow: 'auto'}}>
                        <code>{selectedScript.content}</code>
                      </pre>
                    </div>

                    {selectedScript.compatibility_notes && (
                      <div className="mb-3">
                        <h6>Compatibility Notes</h6>
                        <p className="text-muted">{selectedScript.compatibility_notes}</p>
                      </div>
                    )}
                  </div>
                  
                  <div className="col-md-4">
                    <div className="mb-3">
                      <h6>Script Info</h6>
                      <div className="d-flex justify-content-between mb-1">
                        <span>Type:</span>
                        <span className="badge bg-primary">{selectedScript.script_type}</span>
                      </div>
                      {selectedScript.category && (
                        <div className="d-flex justify-content-between mb-1">
                          <span>Category:</span>
                          <span className="badge bg-info">{selectedScript.category}</span>
                        </div>
                      )}
                      <div className="d-flex justify-content-between mb-1">
                        <span>Version:</span>
                        <span>{selectedScript.version}</span>
                      </div>
                      <div className="d-flex justify-content-between mb-1">
                        <span>Downloads:</span>
                        <span>{selectedScript.download_count}</span>
                      </div>
                      <div className="d-flex justify-content-between mb-1">
                        <span>Author:</span>
                        <span>{selectedScript.author_username}</span>
                      </div>
                    </div>

                    <div className="mb-3">
                      <h6>Rating</h6>
                      <div className="d-flex align-items-center mb-2">
                        {renderStars(selectedScript.rating_average)}
                        <span className="ms-2">
                          {selectedScript.rating_average.toFixed(1)} ({selectedScript.rating_count} reviews)
                        </span>
                      </div>
                      
                      {currentUser && (
                        <div className="d-flex gap-2">
                          {userReview ? (
                            <button
                              className="btn btn-outline-warning btn-sm"
                              onClick={handleEditReview}
                            >
                              <i className="bi bi-pencil me-1"></i>Edit Review
                            </button>
                          ) : (
                            <button
                              className="btn btn-outline-primary btn-sm"
                              onClick={() => setShowReviewModal(true)}
                            >
                              <i className="bi bi-star me-1"></i>Write Review
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    {selectedScript.tags && (
                      <div className="mb-3">
                        <h6>Tags</h6>
                        {renderTags(selectedScript.tags)}
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-4">
                  <h6>Reviews ({scriptReviews.length})</h6>
                  <div style={{maxHeight: '300px', overflow: 'auto'}}>
                    {scriptReviews.length === 0 ? (
                      <p className="text-muted">No reviews yet. Be the first to review!</p>
                    ) : (
                      scriptReviews.map(review => (
                        <div key={review.id} className="border-bottom pb-3 mb-3">
                          <div className="d-flex justify-content-between align-items-start mb-2">
                            <div>
                              <strong>{review.user?.username || 'Anonymous'}</strong>
                              <div className="d-flex align-items-center">
                                {renderStars(review.rating)}
                                <small className="text-muted ms-2">
                                  {new Date(review.created_at).toLocaleDateString()}
                                </small>
                              </div>
                            </div>
                          </div>
                          {review.review_text && (
                            <p className="mb-0 text-muted">{review.review_text}</p>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>
              <div className="modal-footer border-secondary">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowDetailsModal(false);
                    setSelectedScript(null);
                    setScriptReviews([]);
                    setUserReview(null);
                  }}
                >
                  Close
                </button>
                <button
                  type="button"
                  className="btn btn-success"
                  onClick={() => {
                    setShowImportModal(true);
                    setShowDetailsModal(false);
                  }}
                >
                  <i className="bi bi-download me-1"></i>Import Script
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Review Modal */}
      {showReviewModal && selectedScript && (
        <div className="modal show d-block" style={{backgroundColor: 'rgba(0,0,0,0.5)'}}>
          <div className="modal-dialog">
            <div className="modal-content">
              <div className="modal-header border-secondary">
                <h5 className="modal-title">
                  {userReview ? 'Edit Review' : 'Write Review'} - {selectedScript.name}
                </h5>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => {
                    setShowReviewModal(false);
                    setReviewForm({ rating: 5, review_text: '' });
                  }}
                ></button>
              </div>
              <div className="modal-body">
                <div className="mb-3">
                  <label className="form-label">Rating</label>
                  <div className="d-flex align-items-center">
                    {[1, 2, 3, 4, 5].map(star => (
                      <button
                        key={star}
                        type="button"
                        className="btn btn-link p-0 me-1"
                        onClick={() => setReviewForm(prev => ({ ...prev, rating: star }))}
                      >
                        <i 
                          className={`bi bi-star${star <= reviewForm.rating ? '-fill' : ''} text-warning`}
                          style={{fontSize: '1.5rem'}}
                        ></i>
                      </button>
                    ))}
                    <span className="ms-2 text-muted">{reviewForm.rating} star{reviewForm.rating !== 1 ? 's' : ''}</span>
                  </div>
                </div>
                
                <div className="mb-3">
                  <label className="form-label">Review (optional)</label>
                  <textarea
                    className="form-control"
                    rows="4"
                    value={reviewForm.review_text}
                    onChange={(e) => setReviewForm(prev => ({ ...prev, review_text: e.target.value }))}
                    placeholder="Share your experience with this script..."
                  ></textarea>
                </div>
              </div>
              <div className="modal-footer border-secondary">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowReviewModal(false);
                    setReviewForm({ rating: 5, review_text: '' });
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleSubmitReview}
                >
                  {userReview ? 'Update Review' : 'Submit Review'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Marketplace;
