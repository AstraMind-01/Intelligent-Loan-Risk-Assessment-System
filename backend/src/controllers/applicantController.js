const LoanApplication = require('../models/LoanApplication');
const RiskScore = require('../models/RiskScore');
const { sendSuccess, sendError } = require('../utils/responseFormatter');
const mlClientService = require('../services/mlClientService');
const { evaluateApplication } = require('../services/decisionEngineService');
const { logAction } = require('../services/auditService');
const { generateRiskReportPDF } = require('../utils/pdfGenerator');
const { APPLICATION_STATUS } = require('../config/constants');

// @desc    Submit new loan application
// @route   POST /api/applicant/applications
// @access  Private (Applicant)
const submitApplication = async (req, res, next) => {
  try {
    const { personalInfo, financialInfo, notes } = req.body;

    const application = await LoanApplication.create({
      applicantId: req.user._id,
      personalInfo,
      financialInfo,
      notes,
      status: APPLICATION_STATUS.SUBMITTED,
    });

    await logAction({
      actorType: 'System',
      actorId: 'System',
      applicationId: application._id,
      action: 'Application Submitted',
      details: 'Applicant submitted a new loan application.',
    });

    // Fire off async ML risk assessment
    setImmediate(async () => {
      try {
        const riskData = await mlClientService.callPredictRiskScore(application);
        const fraudData = await mlClientService.callFraudCheck(application);
        
        const combinedRisk = {
            ...riskData,
            fraudFlag: fraudData.fraudFlag,
            fraudReason: fraudData.reason
        };

        await RiskScore.create({
          applicationId: application._id,
          ...combinedRisk
        });

        const newStatus = await evaluateApplication(application, combinedRisk);
        
        application.status = newStatus;
        await application.save();

      } catch (err) {
        console.error('Async ML assessment failed:', err);
      }
    });

    sendSuccess(res, 'Application submitted successfully', { application }, 201);
  } catch (error) {
    next(error);
  }
};

// @desc    Get applicant's applications
// @route   GET /api/applicant/applications
// @access  Private (Applicant)
const getMyApplications = async (req, res, next) => {
  try {
    const applications = await LoanApplication.find({ applicantId: req.user._id }).sort('-createdAt');
    sendSuccess(res, 'Applications retrieved', { applications });
  } catch (error) {
    next(error);
  }
};

// @desc    Get single application
// @route   GET /api/applicant/applications/:id
// @access  Private (Applicant)
const getApplication = async (req, res, next) => {
  try {
    const application = await LoanApplication.findOne({ 
      _id: req.params.id, 
      applicantId: req.user._id 
    });

    if (!application) {
      return sendError(res, 'Application not found', 404);
    }

    sendSuccess(res, 'Application retrieved', { application });
  } catch (error) {
    next(error);
  }
};

// @desc    Upload document for application
// @route   POST /api/applicant/applications/:id/documents
// @access  Private (Applicant)
const uploadDocument = async (req, res, next) => {
  try {
    const { type } = req.body;
    
    if (!req.file) {
      return sendError(res, 'Please upload a file', 400);
    }

    const application = await LoanApplication.findOne({ 
      _id: req.params.id, 
      applicantId: req.user._id 
    });

    if (!application) {
      return sendError(res, 'Application not found', 404);
    }

    const newDoc = {
      type: type || 'other',
      fileUrl: req.file.path,
      originalName: req.file.originalname,
      mimeType: req.file.mimetype,
      size: req.file.size,
    };

    application.documents.push(newDoc);
    await application.save();

    await logAction({
      actorType: 'System',
      actorId: 'System',
      applicationId: application._id,
      action: 'Document Uploaded',
      details: `Applicant uploaded document of type: ${type}`,
    });

    sendSuccess(res, 'Document uploaded successfully', { document: newDoc }, 201);
  } catch (error) {
    next(error);
  }
};

// @desc    Get risk report
// @route   GET /api/applicant/applications/:id/risk-report
// @access  Private (Applicant)
const getRiskReport = async (req, res, next) => {
  try {
    const application = await LoanApplication.findOne({ 
      _id: req.params.id, 
      applicantId: req.user._id 
    });

    if (!application) {
      return sendError(res, 'Application not found', 404);
    }

    const riskScore = await RiskScore.findOne({ applicationId: application._id });

    if (!riskScore) {
      return sendError(res, 'Risk report not ready yet', 404);
    }

    sendSuccess(res, 'Risk report retrieved', { riskScore });
  } catch (error) {
    next(error);
  }
};

// @desc    Download risk report PDF
// @route   GET /api/applicant/applications/:id/risk-report/pdf
// @access  Private (Applicant)
const downloadRiskReportPdf = async (req, res, next) => {
  try {
    const application = await LoanApplication.findOne({ 
      _id: req.params.id, 
      applicantId: req.user._id 
    }).populate('applicantId', 'name email');

    if (!application) {
      return sendError(res, 'Application not found', 404);
    }

    const riskScore = await RiskScore.findOne({ applicationId: application._id });

    const doc = generateRiskReportPDF(application, riskScore);

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename=risk-report-${application._id}.pdf`);
    
    doc.pipe(res);
    doc.end();
  } catch (error) {
    next(error);
  }
};

// @desc    Simulate "What If" scenarios
// @route   POST /api/applicant/applications/:id/simulate
// @access  Private (Applicant)
const simulateRisk = async (req, res, next) => {
  try {
    const { income, loanAmountRequested, tenure } = req.body;
    
    const application = await LoanApplication.findOne({ 
      _id: req.params.id, 
      applicantId: req.user._id 
    }).lean();

    if (!application) {
      return sendError(res, 'Application not found', 404);
    }

    // Override with simulation data
    const simulatedData = { ...application };
    simulatedData.financialInfo = {
        ...simulatedData.financialInfo,
        income: income || simulatedData.financialInfo.income,
        loanAmountRequested: loanAmountRequested || simulatedData.financialInfo.loanAmountRequested,
        tenure: tenure || simulatedData.financialInfo.tenure
    };

    const simulatedRisk = await mlClientService.callSimulate(simulatedData);

    sendSuccess(res, 'Simulation complete', { simulatedRisk });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  submitApplication,
  getMyApplications,
  getApplication,
  uploadDocument,
  getRiskReport,
  downloadRiskReportPdf,
  simulateRisk
};
