import React, { useState } from 'react';
import hotels from '../mock/hotels';

// Utility to get unique values for a facet
function getUnique(hotels, key, subkey) {
  const values = hotels.map(h => subkey ? h[key][subkey] : h[key]);
  return Array.from(new Set(values)).filter(Boolean);
}

export default function SearchPage() {
  const [search, setSearch] = useState('');
  const [city, setCity] = useState('');
  const [category, setCategory] = useState('');
  const [rating, setRating] = useState('');

  // Facet options
  const cities = getUnique(hotels, 'Address', 'City');
  const categories = getUnique(hotels, 'Category');
  const ratings = getUnique(hotels, 'Rating').sort((a, b) => b - a);

  // Filtering logic
  const filtered = hotels.filter(hotel => {
    return (
      (!search || hotel.HotelName.toLowerCase().includes(search.toLowerCase()) || hotel.Description.toLowerCase().includes(search.toLowerCase())) &&
      (!city || hotel.Address.City === city) &&
      (!category || hotel.Category === category) &&
      (!rating || String(hotel.Rating) === rating)
    );
  });

  function resetFilters() {
    setSearch('');
    setCity('');
    setCategory('');
    setRating('');
  }

  return (
    <div>
      <h2>Find Your Next Stay</h2>
      <div style={{ marginBottom: '1rem', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search hotels..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ flex: 2, minWidth: 180, padding: '0.5rem' }}
        />
        <select value={city} onChange={e => setCity(e.target.value)} style={{ flex: 1, minWidth: 120 }}>
          <option value="">All Cities</option>
          {cities.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={category} onChange={e => setCategory(e.target.value)} style={{ flex: 1, minWidth: 120 }}>
          <option value="">All Categories</option>
          {categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
        </select>
        <select value={rating} onChange={e => setRating(e.target.value)} style={{ flex: 1, minWidth: 100 }}>
          <option value="">All Ratings</option>
          {ratings.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <button onClick={resetFilters} style={{ flex: 1, minWidth: 80 }}>Reset</button>
      </div>
      <div>
        {filtered.length === 0 && <div>No hotels found. Try adjusting your filters.</div>}
        {filtered.map(hotel => (
          <div key={hotel.HotelId} style={{ border: '1px solid #ccc', borderRadius: 8, marginBottom: 16, padding: 16 }}>
            <h3>{hotel.HotelName}</h3>
            <p>{hotel.Description}</p>
            <p><strong>City:</strong> {hotel.Address.City} | <strong>Category:</strong> {hotel.Category} | <strong>Rating:</strong> {hotel.Rating}</p>
            <div style={{ fontSize: 12, color: '#555' }}>Tags: {hotel.Tags.join(', ')}</div>
          </div>
        ))}
      </div>
    </div>
  );
} 