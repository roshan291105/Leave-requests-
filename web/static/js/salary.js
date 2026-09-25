document.querySelectorAll('[data-salary-form]').forEach((form) => {
  const amounts = Array.from(form.querySelectorAll('[data-salary-amount]'));
  const preview = document.querySelector('[data-salary-net]');
  const status = form.querySelector('[data-salary-status]');
  const paidOn = form.querySelector('[data-salary-paid-on]');
  const currency = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'});
  const refreshAmounts = () => {
    const paise = amounts.map((input) => {
      input.setCustomValidity('');
      if (!/^\d{1,8}(?:\.\d{1,2})?$/.test(input.value)) return null;
      const [whole, fraction = ''] = input.value.split('.');
      return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
    });
    if (paise.some((value) => value === null)) {
      preview.textContent = '—';
      return;
    }
    const net = paise[0] + paise[1] - paise[2];
    amounts[2].setCustomValidity(net < 0 ? 'Deductions cannot exceed basic pay plus allowances.' : '');
    preview.textContent = net < 0 ? 'Check deductions' : currency.format(net / 100);
  };
  const refreshPayment = () => {
    const paid = status.value === 'PAID';
    paidOn.required = paid;
    paidOn.disabled = !paid;
  };
  amounts.forEach((input) => input.addEventListener('input', refreshAmounts));
  status.addEventListener('change', refreshPayment);
  window.addEventListener('pageshow', () => { refreshAmounts(); refreshPayment(); });
  refreshAmounts();
  refreshPayment();
});

document.querySelectorAll('[data-department-salaries]').forEach((form) => {
  const currency = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'});
  const refresh = () => {
    let grandTotal = 0;
    let allValid = true;
    form.querySelectorAll('[data-department-rate-row]').forEach((row) => {
      const input = row.querySelector('[data-department-rate]');
      const valid = input.checkValidity() && /^\d{1,8}(?:\.\d{1,2})?$/.test(input.value);
      if (!valid) {
        row.querySelector('[data-department-total]').textContent = '—';
        allValid = false;
        return;
      }
      const [whole, fraction = ''] = input.value.split('.');
      const total = (Number(whole) * 100 + Number(fraction.padEnd(2, '0'))) * Number(row.dataset.employeeCount);
      grandTotal += total;
      row.querySelector('[data-department-total]').textContent = currency.format(total / 100);
    });
    form.querySelector('[data-department-grand-total]').textContent = allValid ? currency.format(grandTotal / 100) : 'Check salary amounts';
  };
  form.addEventListener('input', refresh);
  window.addEventListener('pageshow', refresh);
  refresh();
});

document.querySelectorAll('[data-bulk-salary-form]').forEach((form) => {
  const selectAll = form.querySelector('[data-salary-select-all]');
  const employees = Array.from(form.querySelectorAll('[data-salary-select]:not(:disabled)'));
  const button = form.querySelector('[data-pay-selected]');
  const currency = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'});
  const refresh = () => {
    const selected = employees.filter((input) => input.checked);
    selectAll.checked = employees.length > 0 && selected.length === employees.length;
    selectAll.indeterminate = selected.length > 0 && selected.length < employees.length;
    button.disabled = selected.length === 0;
    form.querySelector('[data-salary-selection-count]').textContent = `${selected.length} selected`;
    const total = selected.reduce((sum, input) => sum + Number(input.dataset.netPay), 0);
    form.querySelector('[data-salary-selected-total]').textContent = currency.format(total / 100);
  };
  selectAll.addEventListener('change', () => { employees.forEach((input) => { input.checked = selectAll.checked; }); refresh(); });
  employees.forEach((input) => input.addEventListener('change', refresh));
  form.addEventListener('submit', (event) => {
    if (!employees.some((input) => input.checked)) {
      event.preventDefault();
      return;
    }
    const count = employees.filter((input) => input.checked).length;
    const total = form.querySelector('[data-salary-selected-total]').textContent;
    const month = form.elements.salary_month.value;
    if (!window.confirm(`Mark ${count} employee salaries as paid for ${month}, totaling ${total}? This records payment in Dayora only.`)) {
      event.preventDefault();
    }
  }, true);
  window.addEventListener('pageshow', refresh);
  refresh();
});
