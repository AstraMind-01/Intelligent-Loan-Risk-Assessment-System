const mongoose = require('mongoose');
const dotenv = require('dotenv');
const path = require('path');
const User = require('../models/User');

dotenv.config({ path: path.resolve(__dirname, '../../../.env') });

const seedDatabase = async () => {
  try {
    const mongoUri = process.env.MONGODB_URI || 'mongodb://localhost:27017/loan_risk_assessment';
    await mongoose.connect(mongoUri);
    
    console.log('MongoDB Connected...');

    // Clear existing users
    await User.deleteMany();

    // Create Admin
    await User.create({
      name: 'System Admin',
      email: 'admin@loanrisk.com',
      password: 'password123',
      role: 'admin',
    });

    // Create Officer
    await User.create({
      name: 'Loan Officer Sarah',
      email: 'officer@loanrisk.com',
      password: 'password123',
      role: 'officer',
    });

    // Create Applicant
    await User.create({
      name: 'John Applicant',
      email: 'applicant@loanrisk.com',
      password: 'password123',
      role: 'applicant',
    });

    console.log('Database seeded successfully!');
    process.exit();
  } catch (error) {
    console.error('Error seeding database:', error);
    process.exit(1);
  }
};

seedDatabase();
