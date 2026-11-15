/** Taiico mobile navigation: scoped to existing header 122. */
add_action('wp_head', function () { ?>
<style id="taiico-mobile-navigation">
@media(max-width:767px){
#masthead{position:sticky;top:0;z-index:1000;background:#34587C}
body.admin-bar #masthead{top:46px}
#masthead .elementor-122 .elementor-element-fb0b8ea{padding:0!important;margin:0!important;min-height:0!important;background:#34587C!important}
#masthead .elementor-122 .elementor-element-fb0b8ea>.elementor-container{min-height:64px!important;height:64px;display:flex;flex-wrap:nowrap;align-items:center;padding:6px 16px;box-sizing:border-box}
#masthead .elementor-122 .elementor-column>.elementor-widget-wrap{padding:0!important;margin:0!important;align-content:center}
#masthead .elementor-122 .elementor-element-a7d855e{width:52px!important;flex:0 0 52px}
#masthead .elementor-122 .elementor-element-0699fb4{display:block!important;margin:0!important}
#masthead .elementor-122 .elementor-element-0699fb4 img{height:42px!important;width:auto!important;max-width:52px;object-fit:contain}
#masthead .elementor-122 .elementor-element-6f99c37,#masthead .elementor-122 .elementor-element-3eaf7a0{display:none!important}
#masthead .elementor-122 .elementor-element-127a6e5{flex:1 1 auto;width:auto!important;min-width:0}
#masthead .elementor-122 .elementor-element-b892667{width:100%;margin:0!important}
#masthead .hfe-nav-menu__toggle{margin:0 0 0 auto!important;width:48px;height:48px;min-width:48px;display:flex;align-items:center;justify-content:center;padding:0!important;border-radius:50%;background:#283E63!important;color:#fff!important;box-shadow:0 2px 8px #1d2f3e33}
#masthead .hfe-nav-menu-icon{padding:0!important;font-size:22px!important;color:#fff!important}
#masthead .hfe-nav-menu__toggle:focus-visible{outline:3px solid #fff;outline-offset:2px}
#masthead .elementor-element-b892667 nav.hfe-dropdown{position:fixed!important;top:70px!important;left:12px!important;right:12px!important;width:auto!important;max-height:calc(100dvh - 90px);overflow-y:auto!important;overscroll-behavior:contain;background:#fff!important;border-radius:16px;box-shadow:0 12px 32px #1d2f3e33;font-family:Helvetica,Arial,sans-serif}
body.admin-bar #masthead .elementor-element-b892667 nav.hfe-dropdown{top:116px!important;max-height:calc(100dvh - 136px)}
#masthead nav.hfe-dropdown{display:none!important}
#masthead nav.hfe-dropdown.taiico-open{display:block!important;visibility:visible!important;opacity:1!important;height:auto!important;transform:none!important}
#masthead nav.hfe-dropdown.taiico-open>ul{display:block!important;visibility:visible!important;opacity:1!important}
#masthead nav.hfe-dropdown .sub-menu{display:none!important}
#masthead nav.hfe-dropdown .taiico-submenu-open>.sub-menu{display:block!important;height:auto!important;position:static!important;visibility:visible!important;opacity:1!important;width:100%!important}
#masthead nav.hfe-dropdown a{background:#fff!important;color:#1D2F3E!important;min-height:44px;font-family:Helvetica,Arial,sans-serif}
#masthead nav.hfe-dropdown a:focus-visible{outline:2px solid #34587C;outline-offset:-3px}
#masthead nav.hfe-dropdown a:hover{background:#edf3f9!important}
}
</style>
<?php });
add_action('wp_footer', function () { ?>
<script id="taiico-mobile-navigation-a11y">
(function(){function init(){var t=document.querySelector('#masthead .hfe-nav-menu__toggle');if(!t)return;
var n=document.querySelector('#masthead .elementor-element-b892667 nav');
function mobile(){return matchMedia('(max-width:767px)').matches;}
function toggle(){var open=t.getAttribute('aria-expanded')!=='true';t.setAttribute('aria-expanded',String(open));n.classList.toggle('taiico-open',open);}
t.addEventListener('click',function(e){if(mobile()){e.preventDefault();e.stopImmediatePropagation();toggle();}},true);
t.addEventListener('keydown',function(e){if(mobile()&&(e.key==='Enter'||e.key===' ')){e.preventDefault();e.stopImmediatePropagation();toggle();}},true);
n.querySelectorAll('.hfe-has-submenu-container').forEach(function(s){function sub(e){if(!mobile())return;if(e.type==='keydown'&&e.key!=='Enter'&&e.key!==' ')return;e.preventDefault();e.stopImmediatePropagation();var open=s.getAttribute('aria-expanded')!=='true';s.setAttribute('aria-expanded',String(open));s.parentElement.classList.toggle('taiico-submenu-open',open);}s.addEventListener('click',sub,true);s.addEventListener('keydown',sub,true);});
function label(){t.setAttribute('aria-label',t.getAttribute('aria-expanded')==='true'?'Cerrar menú':'Abrir menú');}label();new MutationObserver(label).observe(t,{attributes:true,attributeFilter:['aria-expanded']});
document.addEventListener('keydown',function(e){if(e.key==='Escape'&&t.getAttribute('aria-expanded')==='true'){t.click();t.focus();}});
document.addEventListener('click',function(e){if(matchMedia('(max-width:767px)').matches&&t.getAttribute('aria-expanded')==='true'&&!e.target.closest('#masthead'))t.click();});
}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();})();
</script>
<?php });
