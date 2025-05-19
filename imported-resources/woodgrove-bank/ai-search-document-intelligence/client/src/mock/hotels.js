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

export default hotels; 