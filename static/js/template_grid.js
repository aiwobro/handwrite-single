/* 格线几何计算：浏览器与 Node 测试共用，无 DOM 依赖。 */
(function (root) {
  'use strict';
  function geometry(side) {
    const box = side.body, rows = side.row_count, gap = side.bottom_gap;
    if (!box || !Number.isFinite(box.y) || !Number.isFinite(box.height) || box.height <= 0) throw new Error('请先框选正文区域。');
    if (!Number.isInteger(rows) || rows < 1 || rows > 500) throw new Error('正文行数必须为1至500的整数。');
    if (!['bottom', 'top'].includes(side.body_alignment)) throw new Error('正文对齐方式无效。');
    if (!Number.isInteger(gap) || gap < 0 || gap > 500) throw new Error('距下边线必须为0至500的整数像素。');
    const spacing = box.height / rows;
    const boundaries = Array.from({length: rows + 1}, (_, index) => box.y + index * box.height / rows);
    const anchors = Array.from({length: rows}, (_, index) => side.body_alignment === 'bottom'
      ? boundaries[index + 1] - gap : boundaries[index]);
    return {spacing, boundaries, anchors};
  }
  function validate(side) {
    const result = geometry(side);
    if (!Number.isInteger(side.font_size) || side.font_size < 8 || side.font_size > 500) throw new Error('字号必须为8至500的整数。');
    const gap = side.body_alignment === 'bottom' ? side.bottom_gap : 0;
    if (side.font_size + gap > result.spacing) throw new Error('每格高度不足以容纳字号及下边距，请减少行数、字号或下边距。');
    return result;
  }
  const api = {geometry, validate};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.TemplateGrid = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
