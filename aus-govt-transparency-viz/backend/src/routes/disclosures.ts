import express from 'express';
import { query, validationResult } from 'express-validator';
import { getDisclosures, getDisclosureStats } from '../controllers/disclosureController';

const router = express.Router();

/**
 * GET /api/disclosures
 * Get disclosures with filtering options
 */
router.get('/', [
  // Validation rules
  query('mp_name').optional().isString(),
  query('party').optional().isString(),
  query('electorate').optional().isString(),
  query('category').optional().isString(),
  query('entity').optional().isString(),
  query('start_date').optional().isISO8601(),
  query('end_date').optional().isISO8601(),
  query('limit').optional().isInt({ min: 1, max: 1000 }).toInt(),
  query('offset').optional().isInt({ min: 0 }).toInt()
], async (req, res) => {
  // Check for validation errors
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() });
  }
  
  try {
    const disclosures = await getDisclosures(req.query);
    res.json(disclosures);
  } catch (error) {
    console.error('Error retrieving disclosures:', error);
    res.status(500).json({ error: 'Failed to retrieve disclosures' });
  }
});

/**
 * GET /api/disclosures/stats
 * Get statistics about the disclosure data
 */
router.get('/stats', async (req, res) => {
  try {
    const stats = await getDisclosureStats();
    res.json(stats);
  } catch (error) {
    console.error('Error retrieving disclosure stats:', error);
    res.status(500).json({ error: 'Failed to retrieve disclosure statistics' });
  }
});

export { router as disclosuresRouter }; 