const test = require('node:test');
const assert = require('node:assert/strict');
const Grid = require('../static/js/template_grid.js');

const side = (overrides = {}) => ({body: {x: 40, y: 100, width: 500, height: 1000}, row_count: 14,
  body_alignment: 'bottom', bottom_gap: 3, font_size: 50, ...overrides});

test('grid uses full cell height and does not accumulate rounding', () => {
  const result = Grid.validate(side());
  assert.equal(result.spacing, 1000 / 14);
  assert.equal(result.boundaries.length, 15);
  assert.equal(result.boundaries[0], 100);
  assert.equal(result.boundaries[14], 1100);
  assert.equal(result.anchors.length, 14);
  assert.equal(result.anchors[13], 1097);
  assert.equal(result.anchors[0], 100 + 1000 / 14 - 3);
});

test('font size does not alter cell geometry', () => {
  assert.deepEqual(Grid.validate(side({font_size: 24})), Grid.validate(side({font_size: 50})));
});

test('top alignment anchors at cell tops and ignores bottom gap in fit', () => {
  const result = Grid.validate(side({body_alignment: 'top', bottom_gap: 500}));
  assert.equal(result.anchors[0], 100);
  assert.equal(result.anchors[13], 100 + 13 * 1000 / 14);
});

test('one row uses whole region', () => {
  const result = Grid.validate(side({row_count: 1}));
  assert.equal(result.spacing, 1000);
  assert.deepEqual(result.anchors, [1097]);
});

test('reject invalid geometry, overflow and non-integer settings', () => {
  for (const overrides of [{row_count: 0}, {row_count: 501}, {row_count: 2.5}, {row_count: NaN},
    {bottom_gap: -1}, {bottom_gap: 1.5}, {bottom_gap: 501}, {body_alignment: 'center'},
    {font_size: 71}, {font_size: 0}, {body: null}, {body: {y: 0, height: Infinity}}]) {
    assert.throws(() => Grid.validate(side(overrides)));
  }
});

test('geometry may be previewed while fixing an oversized font', () => {
  const draft = side({font_size: 100});
  assert.equal(Grid.geometry(draft).anchors.length, 14);
  assert.throws(() => Grid.validate(draft));
});
