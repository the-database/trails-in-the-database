import React, { Component } from 'react';
import moment from 'moment';

import skyFcLogo from './img/skyfc.png';
import skyScLogo from './img/skysc.png';
import sky3rdLogo from './img/sky3rd.png';

import csLogo from './img/cs.png';
import cs2Logo from './img/cs2.png';
import cs3Logo from './img/cs3.png';
import cs4Logo from './img/cs4.png';

import soraFcLogo from './img/sorafc.png';
import soraScLogo from './img/sorasc.png';
import sora3rdLogo from './img/sora3rd.jpg';

import zeroLogo from './img/zero.png';
import aoLogo from './img/ao.png';

import senLogo from './img/sen.jpg';
import seniiLogo from './img/senii.jpg';
import seniiiLogo from './img/seniii.png';
import senivLogo from './img/seniv.png';

import hajimariLogo from './img/hajimari.png';



export default class ReleaseTimeline extends Component {

  state = {
    data: [
      {x: moment("2004/06/24", "YYYY/MM/DD").unix(), y: -1, imgPath: soraFcLogo, title: 'Sora no Kiseki FC', index: 1},
      {x: moment("2006/03/29", "YYYY/MM/DD").unix(), y: -2, imgPath: soraScLogo, title: 'Sora no Kiseki SC', index: 2},
      {x: moment("2007/06/28", "YYYY/MM/DD").unix(), y: -1, imgPath: sora3rdLogo, title: 'Sora no Kiseki the 3rd', index: 3},
      {x: moment("2010/09/30", "YYYY/MM/DD").unix(), y: -2, imgPath: zeroLogo, title: 'Zero no Kiseki', index: 4},
      {x: moment("2011/09/29", "YYYY/MM/DD").unix(), y: -1, imgPath: aoLogo, title: 'Ao no Kiseki', index: 5},
      {x: moment("2013/09/26", "YYYY/MM/DD").unix(), y: -2, imgPath: senLogo, title: 'Sen no Kiseki', index: 6},
      {x: moment("2014/09/25", "YYYY/MM/DD").unix(), y: -1, imgPath: seniiLogo, title: 'Sen no Kiseki II', index: 7},
      {x: moment("2017/09/28", "YYYY/MM/DD").unix(), y: -2, imgPath: seniiiLogo, title: 'Sen no Kiseki III', index: 8},
      {x: moment("2018/09/27", "YYYY/MM/DD").unix(), y: -1, imgPath: senivLogo, title: 'Sen no Kiseki IV', index: 9},
      {x: moment("2020/08/27", "YYYY/MM/DD").unix(), y: -2, imgPath: hajimariLogo, title: 'Hajimari no Kiseki', index: 10},

      {x: moment("2011/03/29", "YYYY/MM/DD").unix(), y: 1, imgPath: skyFcLogo, title: 'Trails in the Sky', index: 1},
      {x: moment("2015/10/29", "YYYY/MM/DD").unix(), y: 4, imgPath: skyScLogo, title: 'Trails in the Sky SC', index: 2},
      {x: moment("2017/05/03", "YYYY/MM/DD").unix(), y: 1, imgPath: sky3rdLogo, title: 'Trails in the Sky the 3rd', index: 3},
      {x: moment("2015/12/22", "YYYY/MM/DD").unix(), y: 3, imgPath: csLogo, title: 'Trails of Cold Steel', index: 6},
      {x: moment("2016/09/06", "YYYY/MM/DD").unix(), y: 2, imgPath: cs2Logo, title: 'Trails of Cold Steel II', index: 7},
      {x: moment("2019/10/22", "YYYY/MM/DD").unix(), y: 2, imgPath: cs3Logo, title: 'Trails of Cold Steel III', index: 8},
      {x: moment("2020/10/27", "YYYY/MM/DD").unix(), y: 1, imgPath: cs4Logo, title: 'Trails of Cold Steel IV', index: 9},
    ],
    unreleasedData: [
      {x: moment("2022/01/01", "YYYY/MM/DD").unix(), y: 4, imgPath: null, title: <span>Trails from Zero <sup>[1]</sup></span>, index: 4},
      {x: moment("2022/07/01", "YYYY/MM/DD").unix(), y: 4, imgPath: null, title: <span>Trails to Azure <sup>[2]</sup></span>, index: 5},
      {x: moment("2023/01/01", "YYYY/MM/DD").unix(), y: 4, imgPath: null, title: 'Hajimari no Kiseki', index: 10},
      
      // {x: moment("2021/01/01", "YYYY/MM/DD").unix(), y: 4, imgPath: null, title: 'Trails of Cold Steel IV', index: 9},
    ],
    hovered: null,
  };

  onMouseOver = (index) => {
    this.setState({hovered: index});
  }

  onMouseOut = (index) => {
    this.setState({hovered: null});
  }

  getArcColor = (index) => {
    if (index >= 1 && index <= 3) {
      return 'rgb(51, 122, 183)';
    } else if (index >= 4 && index <= 5) {
      return 'rgb(91, 192, 222)';
    } else {
      return 'rgb(217, 83, 79)';
    }
  }

  getTimeGap = (index) => {
    const filtered = this.state.data.filter(elt => elt.index === index);
    if (filtered.length === 2) {
      const duration = moment.duration(moment.unix(filtered[1].x).diff(moment.unix(filtered[0].x)));
      return `${duration.years()} year${duration.years() !== 1 ? 's' : ''}, ${duration.months()} month${duration.months() !== 1 ? 's' : ''}`;
    } else if (filtered.length === 1) {
      const duration = moment.duration(moment().diff(moment.unix(filtered[0].x)));
      return `N/A (${duration.years()} year${duration.years() !== 1 ? 's' : ''}, ${duration.months()} month${duration.months() !== 1 ? 's' : ''} and counting)`;
    }

    return 'N/A';
  }

  render() {
    const {data} = this.state;
    const xDomain = [moment("2004/06/24", "YYYY/MM/DD").unix(), moment("2018/09/27", "YYYY/MM/DD").unix()]
    const xRange = xDomain[1] - xDomain[0];

    const gridLines = []

    const contentHeight = 135;

    const padding = 10;

    const getLeft = (x) => ((x - xDomain[0]) / xRange * 80 + '%');
    const getTop = (y) => y > 0 ? (y - 1) * contentHeight + this.props.height/2 + padding * (y - 1) : 
                          (y + 1) * contentHeight - contentHeight + this.props.height/2 - padding * Math.abs(y - 1);

    const range = (start, end) => Array.from({length: (end - start)}, (v, k) => k + start);
    
    return (
      <div className="container">
        <h2>Release Timeline</h2>
        <p><small style={{color: 'gray'}}>Hover for details</small></p>
        <div style={{position:'relative', width: '100%', height: this.props.height, textAlign: 'right', marginBottom: '40px'}}>
          {this.state.hovered > 0 ? <div style={{position:'absolute',right:0,top:0}}>
            {data.filter(elt => elt.index === this.state.hovered).map(elt => <h4 key={elt.title}>{elt.title}</h4>)}
            Time to Localize: {this.getTimeGap(this.state.hovered)}
          </div> : null}
          {data.map((elt, i) => (
            [
              <div key={i+"-"+1} style={{position:'absolute', 
                            top: `calc(${getLeft(elt.x)} - 0px)`, 
                            left: getTop(elt.y), 
                            lineHeight: 1.25,
                            // right: getTop(elt.y),
                            // backgroundColor: 'white', 
                            // border: '1px solid #ccc', borderRadius: '.5rem', 
                            // border:0,
                            // opacity: '0.2',
                            // padding:5, 
                            textAlign: elt.y > 0 ? 'right' : 'left',
                            // width: contentHeight - padding
                            outline: this.state.hovered === elt.index ? '4px solid ' + this.getArcColor(elt.index) : 'none'
                            }}
                    onMouseOver={ () => this.onMouseOver(elt.index) }
                    onMouseOut={ () => this.onMouseOut(elt.index) }>
                <div style={{fontSize:'80%', padding: 5, fontWeight:'bold', }}>
                  <small>{elt.index}.</small> {elt.title}<br/>
                  <small>{moment.unix(elt.x).format('YYYY/MM/DD')}</small>
                </div>
                <img className="logo" style={{maxHeight: 50, maxWidth: 100}} src={elt.imgPath}/> <br/>
                
              </div>,
              <div key={i+"-"+2}  className="small" style={{ zIndex: -1, position: 'absolute', 
                            // width: elt.y > 0 ? Math.abs(elt.y * contentHeight) + contentHeight : Math.abs(elt.y) -1 * contentHeight, 
                            width: contentHeight * Math.abs(elt.y) + (Math.abs(elt.y) - (elt.y / Math.abs(elt.y))) * padding,
                            height:2, 
                            backgroundColor: '#ccc', 
                            left: elt.y < 0 ? getTop(elt.y) : this.props.height/2, 
                            top: `calc(${getLeft(elt.x)} - 1px)`,
                             }}>
              </div>
            ]
          ))}

          <div style={{color:'gray'}} className='small'>
                      <div  style={{position:'absolute', 
                            top: `calc(${getLeft(moment("2021/07/01", "YYYY/MM/DD").unix())} - 0px)`, 
                            left: getTop(4), 
                            lineHeight: 1.25,
                            textAlign: 'right',
                            }}
                    >
                    Not yet officially localized:
                    </div>
          {this.state.unreleasedData.map((elt, i) => (
            [
              <div key={i+"-"+3} style={{position:'absolute', 
                            top: `calc(${getLeft(elt.x)} - 0px)`, 
                            left: getTop(elt.y), 
                            lineHeight: 1.25,
                            textAlign: elt.y > 0 ? 'right' : 'left',
                            outline: this.state.hovered === elt.index ? '4px solid ' + this.getArcColor(elt.index) : 'none'
                            }}
                    onMouseOver={ () => this.onMouseOver(elt.index) }
                    onMouseOut={ () => this.onMouseOut(elt.index) }>
                <div style={{fontSize:'80%', padding: 5, fontWeight:'bold', }}>
                  <small>{elt.index}.</small> {elt.title}<br/>
                </div>
              </div>,
            ]
          ))}
          </div>
          <hr style={{margin: 0, position:'absolute', left:this.props.height/2, top:0, height: '100%', width: 2, backgroundColor: '#ccc'}}/>
          {range(2005,2020).map(year => {
            const time = moment(`${year}/01/01`, "YYYY/MM/DD").unix();
            return [<div key={year} style={{margin: 0, position: 'absolute', left: this.props.height/2 - 300, top: getLeft(time), width:870, height:1, backgroundColor: '#eee', zIndex: -1}} />]
          })}
          <div style={{fontSize:'80%', color: 'gray', position:'absolute',left:getTop(4),top: `calc(${getLeft(moment("2024/07/01", "YYYY/MM/DD").unix())} - 0px)`, textAlign:'left'}}>
            <small>
            [1] Trails from Zero <strong>Geofront</strong> patch released 03/15/2020<br/>
            [2] Trails to Azure <strong>Guren/Flame</strong> patch released in 2018; <br/>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Trails to Azure <strong>Geofront</strong> patch in progress
            </small>
          </div>
        </div>
      </div>
    );
  }
}

/*

        <XYPlot yDomain={[-1, 22]} xDomain={[-1, 5]} width={300} height={300}>
          <XAxis />
          <YAxis />
          <MarkSeries
            className="mark-series-example"
            strokeWidth={2}
            sizeRange={[5, 15]}
            data={data}
          />
          <LabelSeries animation allowOffsetToBeReversed data={data} />
        </XYPlot>

*/