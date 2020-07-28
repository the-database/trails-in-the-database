import React, { Component } from 'react';

import jpnFlag from './img/jpn.png';
import usaFlag from './img/usa.png';

import skyFcLogo from './img/skyfc.png';
import skyScLogo from './img/skysc.png';
import sky3rdLogo from './img/sky3rd.png';

import csLogo from './img/cs.png';
import cs2Logo from './img/cs2.png';

import zeroLogo from './img/zero.png';
import aoLogo from './img/ao.png';

import seniiiLogo from './img/seniii.png';

import grid20 from './img/grid-20.png';

export default class InGameTimeline extends Component {
  render() {
    return (
      <div className="container">
        <h2>In-Game Timeline</h2>
        <div>
          <section className="content">
            <div className="columns">
              <section className="side-col">
                <div>
                </div>
              </section>
              <section className="content-col" style={{order: 2}}>
                <div style={{background: '#337ab7', borderColor: '#2e6da4', padding: 10, color: 'white'}}>
                  The Legend of Heroes VI<br />
                  <small style={{opacity: '.7'}}>英雄伝説VI・Eiyuu Densetsu VI</small>
                </div>
              </section>
              <section className="content-col" style={{order: 3}}>
                <div style={{background: '#5bc0de', borderColor: '#4cae4c', padding: 10, color: 'white'}}>
                  The Legend of Heroes VII<br />
                  <small style={{opacity: '.7'}}>英雄伝説VII・Eiyuu Densetsu VII</small>
                </div>
              </section>
              <section className="content-col" style={{order: 4}}>
                <div style={{background: '#d9534f', borderColor: '#d43f3a', padding: 10, color: 'white'}}>
                  The Legend of Heroes VIII<br />
                  <small style={{opacity: '.7'}}>英雄伝説VIII・Eiyuu Densetsu VIII</small>
                </div>
              </section>
            </div>
          </section>
        </div>

        <div className="wrapper">
          <section className="content">
            <div className="columns">
              <section className="side-col">
                <div>
                  <div className="" style={{height:240, borderTop: '3px solid rgba(0,0,0,.2)'}}>S1202</div>
                  <div className="" style={{height:240, borderTop: '3px solid rgba(0,0,0,.2)'}}>S1203</div>
                  <div className="" style={{height:240, borderTop: '3px solid rgba(0,0,0,.2)'}}>S1204</div>
                  <div className="" style={{height:240, borderTop: '3px solid rgba(0,0,0,.2)'}}>S1205</div>
                  <div className="" style={{height:240, borderTop: '3px solid rgba(0,0,0,.2)'}}>S1206</div>
                  <div className="" style={{height:12, borderTop: '3px solid rgba(0,0,0,.2)'}}></div>
                </div>
              </section>

              <section className="content-col" style={{order: 2}}>
                <div className="show-grid loh-6" style={{height: 160}}>
                  <h4 style={{}}><span className="number">1</span> Trails in the Sky <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> 2011/03/29</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>空の軌跡FC ・ Sora no Kiseki FC<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2004/06/24</span></small></h4>
                  <img alt="Trails in the Sky FC Logo" className="logo" style={{maxWidth: '100%'}} src={skyFcLogo} />
                </div>
                <div className="show-grid loh-6" style={{height: 160}}>
                  <h4 style={{}}><span className="number">2</span> Trails in the Sky SC <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> 2015/10/29</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>空の軌跡SC ・ Sora no Kiseki SC<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2006/03/09</span></small></h4>
                  <img alt="Trails in the Sky SC Logo" className="logo" style={{maxWidth: '100%'}} src={skyScLogo} />
                </div>
                <div style={{height: 140}} />
                <div className="show-grid" style={{height: 160, padding: 0, border: 0, background: 'white'}}>
                  <div className="show-grid loh-6" style={{height: 5, padding: 0}}>
                    <h4 style={{}}><span className="number">3</span> Trails in the Sky the 3rd <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> 2017/05/03</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>空の軌跡 the 3rd ・ Sora no Kiseki the 3rd<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2007/06/28</span></small></h4>
                    <img alt="Trails in the Sky the 3rd Logo" className="logo" style={{maxWidth: '100%'}} src={sky3rdLogo} />
                  </div>
                </div>
              </section>
              <section className="content-col" style={{order: 3}}>
                <div style={{height: 480}} />
                <div className="show-grid loh-7" style={{height: 100}}>
                  <h4 style={{}}><span className="number">4</span> Trails from Zero <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> - &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>零の軌跡 ・ Zero no Kiseki<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2010/09/30</span></small></h4>
                  <img alt="Trails from Zero Logo" className="logo" style={{maxWidth: '100%'}} src={zeroLogo} />
                </div>
                <div style={{height: 40}} />
                <div className="show-grid loh-7" style={{height: 100}}>
                  <h4 style={{}}><span className="number">5</span> Trails to Azure <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> - &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>碧の軌跡 ・ Ao no Kiseki<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2011/09/29</span></small></h4>
                  <img alt="Trails to Azure Logo" className="logo" style={{maxWidth: '100%', width: 150}} src={aoLogo} />
                </div>
              </section>
              <section className="content-col" style={{order: 4}}>
                <div style={{height: 520}} />
                <div className="show-grid loh-8" style={{height: 140}}>
                  <h4 style={{}}><span className="number">6</span> Trails of Cold Steel <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> 2015/12/22</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>閃の軌跡 ・ Sen no Kiseki<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2013/09/26</span></small></h4>
                  <img alt="Trails of Cold Steel Logo" className="logo" style={{maxWidth: '100%', width: 160}} src={csLogo} />
                </div>
                <div style={{height: 20}} />
                <div className="show-grid" style={{height: 160, padding: 0, border: 0, background: 'white'}}>
                  <div className="show-grid loh-8" style={{height: 80}}>
                    <h4 style={{}}><span className="number">7</span> Trails of Cold Steel II <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> 2016/09/06</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>閃の軌跡II ・ Sen no Kiseki II<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2014/09/25</span></small></h4>
                    <img alt="Trails of Cold Steel II Logo" className="logo" style={{maxWidth: '100%'}} src={cs2Logo} /> 
                  </div>
                </div>
                <div style={{height: 180}} />
                <div className="show-grid loh-8" style={{height: 72}}>
                  <h4 style={{}}><span className="number">8</span> Trails of Cold Steel III <small style={{color: 'rgba(0,0,0,0.5)', float: 'right'}}><img className="flag" src={usaFlag} alt="USA Flag" /> - &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</small> <small style={{color: 'rgba(0,0,0,.5)', display: 'block', paddingLeft: 16}}>閃の軌跡III ・ Sen no Kiseki III<span style={{float: 'right'}}><img className="flag" src={jpnFlag} alt="JPN Flag" /> 2017/09/28</span></small></h4>
                  <img alt="Trails of Cold Steel III Logo" className="logo" style={{maxWidth: '100%'}} src={seniiiLogo} />
                </div>
              </section>
              
              <div style={{width: '93%', position: 'absolute', right: 0}}>
                <div style={{top: 0, position: 'absolute', height: 240, width: '100%', borderTop: '3px solid rgba(0,0,0,.2)', background: `url("${grid20}")`, zIndex: 1}} />
                <div style={{top: 240, position: 'absolute', height: 240, width: '100%', borderTop: '3px solid rgba(0,0,0,.2)', background: `url("${grid20}")`, zIndex: 1}} />
                <div style={{top: 480, position: 'absolute', height: 240, width: '100%', borderTop: '3px solid rgba(0,0,0,.2)', background: `url("${grid20}")`, zIndex: 1}} />
                <div style={{top: 720, position: 'absolute', height: 240, width: '100%', borderTop: '3px solid rgba(0,0,0,.2)', background: `url("${grid20}")`, zIndex: 1}} />
                <div style={{top: 960, position: 'absolute', height: 240, width: '100%', borderTop: '3px solid rgba(0,0,0,.2)', background: `url("${grid20}")`, zIndex: 1}} />
                <div style={{top: 1200, position: 'absolute', height: 12, width: '100%', borderTop: '3px solid rgba(0,0,0,.2)', zIndex: 1}} />
              </div>
            </div>
          </section>
        </div>
      </div>
    );
  }
}