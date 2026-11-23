// Password show/hide toggle — .pw-field wrapper ke andar .pw-eye button
// (login, change-password, users pages pe kaam karta hai)
document.addEventListener('click', function (e) {
  var btn = e.target.closest('.pw-eye');
  if (!btn) return;
  var field = btn.parentElement;
  var inp = field && field.querySelector('input');
  if (!inp) return;
  var show = inp.type === 'password';
  inp.type = show ? 'text' : 'password';
  btn.textContent = show ? '🙈' : '👁';
  btn.title = show ? 'Hide password' : 'Show password';
  inp.focus();
});
