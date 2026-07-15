/**
 * Monitoring Substansi Nilai Mahasiswa
 * script.js — GPA Calculator & interactive UI
 */

// ─── Constants ────────────────────────────────────────────────────────────────
const DEFAULT_COURSE_ROWS = 3;

const PREDIKAT_THRESHOLDS = [
  { min: 3.51, label: '🏅 Cum Laude (Dengan Pujian)',    color: '#065f46' },
  { min: 3.01, label: '🎓 Sangat Memuaskan',             color: '#1e40af' },
  { min: 2.76, label: '✅ Memuaskan',                    color: '#713f12' },
  { min: 2.00, label: '📘 Cukup',                        color: '#7c2d12' },
  { min: 0,    label: '⚠️ Di Bawah Batas Kelulusan',    color: '#b91c1c' },
];

// ─── Grade data ───────────────────────────────────────────────────────────────
const GRADE_DATA = [
  { grade: 'A',  point: 4.00, range: '85 – 100', quality: 'Istimewa',       barClass: 'bar-A',   badgeClass: 'grade-A',   width: 100 },
  { grade: 'A-', point: 3.75, range: '80 – 84',  quality: 'Sangat Baik+',  barClass: 'bar-A-',  badgeClass: 'grade-A-',  width: 93  },
  { grade: 'B+', point: 3.50, range: '75 – 79',  quality: 'Baik+',         barClass: 'bar-Bp',  badgeClass: 'grade-Bp',  width: 87  },
  { grade: 'B',  point: 3.00, range: '70 – 74',  quality: 'Baik',          barClass: 'bar-B',   badgeClass: 'grade-B',   width: 75  },
  { grade: 'B-', point: 2.75, range: '65 – 69',  quality: 'Baik-',         barClass: 'bar-B-',  badgeClass: 'grade-B-',  width: 68  },
  { grade: 'C+', point: 2.50, range: '60 – 64',  quality: 'Cukup+',        barClass: 'bar-Cp',  badgeClass: 'grade-Cp',  width: 62  },
  { grade: 'C',  point: 2.00, range: '55 – 59',  quality: 'Cukup',         barClass: 'bar-C',   badgeClass: 'grade-C',   width: 50  },
  { grade: 'D',  point: 1.00, range: '40 – 54',  quality: 'Kurang',        barClass: 'bar-D',   badgeClass: 'grade-D',   width: 25  },
  { grade: 'E',  point: 0.00, range: '0 – 39',   quality: 'Tidak Lulus',   barClass: 'bar-E',   badgeClass: 'grade-E',   width: 0   },
];

// ─── Build grade table ────────────────────────────────────────────────────────
function buildGradeTable() {
  const tbody = document.getElementById('grade-tbody');
  if (!tbody) return;

  GRADE_DATA.forEach(g => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <span class="grade-badge ${g.badgeClass}">${g.grade}</span>
      </td>
      <td>${g.range}</td>
      <td><strong>${g.point.toFixed(2)}</strong></td>
      <td>
        <div class="quality-bar">
          <div class="bar">
            <div class="bar-fill ${g.barClass}" style="width:0%" data-width="${g.width}%"></div>
          </div>
          <span class="quality-label">${g.quality}</span>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Animate bars after a short delay
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      document.querySelectorAll('.bar-fill').forEach(el => {
        el.style.width = el.dataset.width;
      });
    });
  });
}

// ─── Accordion (criteria) ─────────────────────────────────────────────────────
function initAccordion() {
  document.querySelectorAll('.criteria-header').forEach(header => {
    header.addEventListener('click', () => {
      const item = header.closest('.criteria-item');
      const isOpen = item.classList.contains('open');

      // Close all
      document.querySelectorAll('.criteria-item.open').forEach(i => i.classList.remove('open'));

      // Toggle clicked
      if (!isOpen) item.classList.add('open');
    });
  });

  // Open first by default
  const first = document.querySelector('.criteria-item');
  if (first) first.classList.add('open');
}

// ─── GPA Calculator ───────────────────────────────────────────────────────────
let courseCount = 0;

function addCourseRow(name = '', sks = '', grade = '') {
  courseCount++;
  const container = document.getElementById('courses-container');
  const row = document.createElement('div');
  row.className = 'course-row';
  row.dataset.id = courseCount;

  const gradeOptions = GRADE_DATA.map(g =>
    `<option value="${g.point}" ${grade === g.point.toString() ? 'selected' : ''}>${g.grade} (${g.point.toFixed(2)})</option>`
  ).join('');

  row.innerHTML = `
    <input type="text" placeholder="Nama Mata Kuliah" value="${name}" aria-label="Nama Mata Kuliah" />
    <select aria-label="Nilai Huruf">
      <option value="" disabled ${!grade ? 'selected' : ''}>Nilai</option>
      ${gradeOptions}
    </select>
    <input type="number" placeholder="SKS (1-6)" value="${sks}" min="1" max="6" aria-label="SKS" />
    <button class="btn btn-danger" onclick="removeCourseRow(this)" title="Hapus" aria-label="Hapus mata kuliah">
      &times;
    </button>
  `;
  container.appendChild(row);
}

function removeCourseRow(btn) {
  btn.closest('.course-row').remove();
  if (document.querySelectorAll('.course-row').length === 0) {
    clearResult();
  }
}

function clearResult() {
  const result = document.getElementById('gpa-result');
  if (result) result.style.display = 'none';
}

function resetCalculator() {
  document.getElementById('courses-container').innerHTML = '';
  courseCount = 0;
  clearResult();
  for (let i = 0; i < DEFAULT_COURSE_ROWS; i++) addCourseRow();
}

function calculateGPA() {
  const rows = document.querySelectorAll('.course-row');
  let totalMutu = 0;
  let totalSKS = 0;
  let valid = 0;
  let errors = [];

  rows.forEach((row, i) => {
    const gradeEl = row.querySelector('select');
    const sksEl   = row.querySelector('input[type="number"]');
    const nameEl  = row.querySelector('input[type="text"]');

    const gradeVal = gradeEl ? parseFloat(gradeEl.value) : NaN;
    const sksVal   = sksEl   ? parseInt(sksEl.value, 10)  : NaN;
    const name     = nameEl  ? nameEl.value.trim()        : '';

    if (!gradeEl.value && !sksEl.value && !name) return; // skip empty rows

    if (isNaN(gradeVal) || gradeEl.value === '') {
      errors.push(`Baris ${i + 1}: Nilai belum dipilih.`);
      return;
    }
    if (isNaN(sksVal) || sksVal < 1 || sksVal > 6) {
      errors.push(`Baris ${i + 1}: SKS tidak valid (harus 1–6).`);
      return;
    }

    totalMutu += gradeVal * sksVal;
    totalSKS  += sksVal;
    valid++;
  });

  if (errors.length > 0) {
    alert('Terdapat kesalahan input:\n' + errors.join('\n'));
    return;
  }

  if (valid === 0 || totalSKS === 0) {
    alert('Harap isi setidaknya satu mata kuliah dengan nilai dan SKS yang valid.');
    return;
  }

  const ipk = totalMutu / totalSKS;
  showGPAResult(ipk, totalSKS, valid);
}

function showGPAResult(ipk, totalSKS, jumlahMK) {
  const result = document.getElementById('gpa-result');
  result.style.display = 'block';

  document.getElementById('gpa-number').textContent = ipk.toFixed(2);

  const predikat = getPredikat(ipk);
  const predikatEl = document.getElementById('gpa-predikat');
  predikatEl.textContent = predikat.label;
  predikatEl.style.color = predikat.color;

  document.getElementById('gpa-detail').textContent =
    `Total SKS: ${totalSKS}  •  Jumlah Mata Kuliah: ${jumlahMK}  •  Total Mutu: ${(ipk * totalSKS).toFixed(2)}`;

  result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function getPredikat(ipk) {
  return PREDIKAT_THRESHOLDS.find(p => ipk >= p.min) || PREDIKAT_THRESHOLDS[PREDIKAT_THRESHOLDS.length - 1];
}

// ─── Score converter ──────────────────────────────────────────────────────────
function initScoreConverter() {
  const input  = document.getElementById('score-input');
  const output = document.getElementById('score-output');
  if (!input || !output) return;

  input.addEventListener('input', () => {
    const val = parseFloat(input.value);
    if (isNaN(val) || val < 0 || val > 100) {
      output.textContent = '—';
      output.className = 'converter-result';
      return;
    }

    const found = GRADE_DATA.find(g => {
      const [low, high] = g.range.split('–').map(s => parseFloat(s.trim()));
      return val >= low && val <= high;
    });

    if (found) {
      output.textContent = `${found.grade}  (${found.point.toFixed(2)}) — ${found.quality}`;
      output.className = `converter-result grade-badge ${found.badgeClass}`;
      output.style.width = 'auto';
      output.style.height = 'auto';
      output.style.padding = '0.35rem 0.9rem';
      output.style.borderRadius = '8px';
      output.style.display = 'inline-block';
      output.style.fontSize = '1rem';
    } else {
      output.textContent = 'Nilai tidak valid';
      output.className = 'converter-result';
    }
  });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildGradeTable();
  initAccordion();
  initScoreConverter();

  // Default calculator rows
  for (let i = 0; i < DEFAULT_COURSE_ROWS; i++) addCourseRow();

  // Attach calculator buttons
  document.getElementById('btn-add-course')?.addEventListener('click', () => addCourseRow());
  document.getElementById('btn-calculate')?.addEventListener('click', calculateGPA);
  document.getElementById('btn-reset')?.addEventListener('click', resetCalculator);
});
