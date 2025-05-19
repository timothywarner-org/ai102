const express = require('express');
const morgan = require('morgan');
const cors = require('cors');
const dotenv = require('dotenv');
const os = require('os');
const { exec } = require('child_process');

// Load environment variables
dotenv.config();

const PORT = process.env.PORT || 3010;

// Idempotent startup: kill any process on PORT
function cleanupPort() {
  return new Promise((resolve) => {
    console.log(`🔄 Checking for existing processes on port ${PORT}...`);
    const isWindows = os.platform() === 'win32';
    if (isWindows) {
      exec(`netstat -ano | findstr :${PORT}`, (error, stdout) => {
        if (error || !stdout) {
          console.log(`✅ No existing processes found on port ${PORT}`);
          return resolve();
        }
        const pidRegex = /LISTENING\s+(\d+)/g;
        const pids = new Set();
        let match;
        while ((match = pidRegex.exec(stdout)) !== null) {
          pids.add(match[1]);
        }
        if (pids.size === 0) {
          console.log('✅ No processes to kill');
          return resolve();
        }
        pids.forEach(pid => {
          console.log(`🛑 Killing process ${pid}...`);
          exec(`taskkill /F /PID ${pid}`, (killError) => {
            if (killError) {
              console.log(`⚠️ Error killing process ${pid}: ${killError.message}`);
            } else {
              console.log(`✅ Successfully killed process ${pid}`);
            }
          });
        });
        setTimeout(resolve, 1000);
      });
    } else {
      exec(`lsof -i :${PORT} | grep LISTEN | awk '{print $2}'`, (error, stdout) => {
        if (error || !stdout) {
          console.log(`✅ No existing processes found on port ${PORT}`);
          return resolve();
        }
        const pids = stdout.trim().split('\n');
        if (pids.length === 0 || (pids.length === 1 && !pids[0])) {
          console.log('✅ No processes to kill');
          return resolve();
        }
        pids.forEach(pid => {
          console.log(`🛑 Killing process ${pid}...`);
          exec(`kill -9 ${pid}`, (killError) => {
            if (killError) {
              console.log(`⚠️ Error killing process ${pid}: ${killError.message}`);
            } else {
              console.log(`✅ Successfully killed process ${pid}`);
            }
          });
        });
        setTimeout(resolve, 1000);
      });
    }
  });
}

const app = express();
app.use(morgan('dev'));
app.use(cors());
app.use(express.json());

// Mock hotel data (same as frontend)
const hotels = [
  {
    HotelId: '1',
    HotelName: 'Stay-Kay City Hotel',
    Description: 'Ideally located on the main commercial artery of the city in the heart of New York.',
    Category: 'Luxury',
    Tags: ['Free wifi', 'On-site parking', 'Indoor pool', 'Continental breakfast'],
    ParkingIncluded: true,
    SmokingAllowed: false,
    LastRenovationDate: '2018-05-01',
    Rating: 4.7,
    Address: {
      StreetAddress: '677 5th Ave',
      City: 'New York',
      StateProvince: 'NY',
      PostalCode: '10022',
      Country: 'USA'
    },
    Location: { type: 'Point', coordinates: [-73.974, 40.763] },
    Rooms: [
      { Description: 'Budget Room, 1 Queen Bed (Cityside)', Type: 'Budget', BaseRate: 96.99, BedOptions: 'Queen', SleepsCount: 2, SmokingAllowed: false },
      { Description: 'Deluxe Room, 2 Double Beds (City View)', Type: 'Deluxe', BaseRate: 150.99, BedOptions: 'Double', SleepsCount: 4, SmokingAllowed: false }
    ]
  },
  {
    HotelId: '2',
    HotelName: 'Woodgrove Grand Resort',
    Description: 'A premium resort experience for Woodgrove Bank customers. Ocean views and world-class amenities.',
    Category: 'Resort',
    Tags: ['Spa', 'Ocean view', 'Free breakfast', 'Pet friendly'],
    ParkingIncluded: true,
    SmokingAllowed: false,
    LastRenovationDate: '2022-03-15',
    Rating: 4.9,
    Address: {
      StreetAddress: '123 Seaside Blvd',
      City: 'Miami',
      StateProvince: 'FL',
      PostalCode: '33139',
      Country: 'USA'
    },
    Location: { type: 'Point', coordinates: [-80.130, 25.790] },
    Rooms: [
      { Description: 'Suite, 1 King Bed, Ocean View', Type: 'Suite', BaseRate: 299.99, BedOptions: 'King', SleepsCount: 2, SmokingAllowed: false },
      { Description: 'Family Room, 2 Queen Beds', Type: 'Family', BaseRate: 199.99, BedOptions: 'Queen', SleepsCount: 4, SmokingAllowed: false }
    ]
  },
  {
    HotelId: '3',
    HotelName: 'Budget Inn Downtown',
    Description: 'Affordable comfort in the heart of the city. Perfect for business travelers and students.',
    Category: 'Budget',
    Tags: ['Free parking', 'Breakfast included'],
    ParkingIncluded: true,
    SmokingAllowed: true,
    LastRenovationDate: '2015-09-10',
    Rating: 3.8,
    Address: {
      StreetAddress: '456 Main St',
      City: 'Chicago',
      StateProvince: 'IL',
      PostalCode: '60616',
      Country: 'USA'
    },
    Location: { type: 'Point', coordinates: [-87.624, 41.856] },
    Rooms: [
      { Description: 'Standard Room, 1 Double Bed', Type: 'Standard', BaseRate: 79.99, BedOptions: 'Double', SleepsCount: 2, SmokingAllowed: true }
    ]
  }
];

// Utility for unique facet values
function getUnique(hotels, key, subkey) {
  const values = hotels.map(h => subkey ? h[key][subkey] : h[key]);
  return Array.from(new Set(values)).filter(Boolean);
}

app.get('/', (req, res) => {
  res.json({ status: 'ok', message: 'Woodgrove Bank AI-102 API server running.' });
});

// /api/search: POST or GET with query params
app.post('/api/search', (req, res) => {
  const { search = '', city = '', category = '', rating = '' } = req.body;
  let filtered = hotels.filter(hotel => {
    return (
      (!search || hotel.HotelName.toLowerCase().includes(search.toLowerCase()) || hotel.Description.toLowerCase().includes(search.toLowerCase())) &&
      (!city || hotel.Address.City === city) &&
      (!category || hotel.Category === category) &&
      (!rating || String(hotel.Rating) === String(rating))
    );
  });
  // Facet counts for UI
  const facetCounts = {
    cities: getUnique(filtered, 'Address', 'City'),
    categories: getUnique(filtered, 'Category'),
    ratings: getUnique(filtered, 'Rating').sort((a, b) => b - a)
  };
  res.json({ results: filtered, facetCounts });
});

// /api/analyze-receipt: POST (mocked, no file handling for now)
app.post('/api/analyze-receipt', (req, res) => {
  res.json({
    hotelName: 'Stay-Kay City Hotel',
    date: '2024-06-01',
    amount: '$189.99',
    notes: 'This is a mocked analysis result.'
  });
});

// /api/hotel/:id: GET
app.get('/api/hotel/:id', (req, res) => {
  const hotel = hotels.find(h => h.HotelId === req.params.id);
  if (!hotel) return res.status(404).json({ error: 'Hotel not found' });
  res.json(hotel);
});

cleanupPort().then(() => {
  app.listen(PORT, () => {
    const line = '='.repeat(60);
    console.log(`\n${line}`);
    console.log('  🏦 Woodgrove Bank AI-102 REST API Server');
    console.log(`  🌐 http://localhost:${PORT}`);
    console.log('  🔄 Morgan logging enabled');
    console.log('  🟢 Ready for requests!');
    console.log(`${line}\n`);
  });
}); 