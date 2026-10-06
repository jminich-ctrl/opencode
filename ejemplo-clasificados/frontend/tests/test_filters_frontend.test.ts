import { describe, it, expect } from 'vitest';
import { filterAdsByCategory } from '../src/pages/AdsList';

// Mock data for ads
const mockAds = [
  { id: 1, title: 'Anuncio 1', category: 'Electronics' },
  { id: 2, title: 'Anuncio 2', category: 'Furniture' },
  { id: 3, title: 'Anuncio 3', category: 'Electronics' },
  { id: 4, title: 'Anuncio 4', category: 'Clothing' },
];

describe('TestFiltersFrontend', () => {
  describe('filterAdsByCategory', () => {
    it('should filter ads by category correctly', () => {
      const result = filterAdsByCategory(mockAds, 'Electronics');
      expect(result).toHaveLength(2);
      expect(result[0].title).toBe('Anuncio 1');
      expect(result[1].title).toBe('Anuncio 3');
    });

    it('should return empty array when no ads match category', () => {
      const result = filterAdsByCategory(mockAds, 'Books');
      expect(result).toHaveLength(0);
    });

    it('should return all ads when category matches all', () => {
      const result = filterAdsByCategory(mockAds, 'Electronics');
      expect(result).toHaveLength(2);
    });

    it('should return all ads when category is empty string', () => {
      const result = filterAdsByCategory(mockAds, '');
      expect(result).toHaveLength(0);
    });
  });
});